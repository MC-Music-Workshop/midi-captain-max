//! MIDI Learn (#54): capture the next MIDI message the device receives.
//!
//! No new firmware protocol: `code.py`'s `_process_midi_msg` already logs every
//! message it handles to the serial console, e.g.
//!
//! ```text
//! [MIDI RX USB] Ch1 CC20=127
//! [MIDI RX DIN] Ch3 NoteOn60 vel100
//! [MIDI RX USB] Ch1 NoteOff60
//! [MIDI RX USB] Ch1 PC5
//! ```
//!
//! Learn opens the console (no Ctrl-C — `code.py` keeps running) and returns
//! the first such line. Those print formats are therefore a contract with
//! `parse_rx_line` below.

use crate::commands::{open_device_serial, validate_device_path, verify_device_connected, ConfigError};
use serde::Serialize;
use std::io::Read;
use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant};
use tauri::command;

const LEARN_TIMEOUT: Duration = Duration::from_secs(30);

static LEARN_CANCEL: AtomicBool = AtomicBool::new(false);

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct LearnedMidi {
    /// Button `type` this message maps to: "cc", "note" or "pc".
    #[serde(rename = "type")]
    pub kind: &'static str,
    /// 0-15, the config's channel encoding.
    pub channel: u8,
    /// CC number, note number or program.
    pub number: u8,
    /// CC value or note velocity; `None` for PC and NoteOff.
    pub value: Option<u8>,
    /// "USB" or "DIN".
    pub source: String,
}

fn midi_byte(s: &str) -> Option<u8> {
    s.parse::<u8>().ok().filter(|v| *v <= 127)
}

/// Parse one `[MIDI RX <source>] Ch<n> <message>` console line.
fn parse_rx_line(line: &str) -> Option<LearnedMidi> {
    let rest = line.trim().strip_prefix("[MIDI RX ")?;
    let (source, rest) = rest.split_once("] ")?;
    let mut tokens = rest.split_whitespace();
    let channel = tokens.next()?.strip_prefix("Ch")?.parse::<u8>().ok()?;
    if !(1..=16).contains(&channel) {
        return None;
    }
    let msg = tokens.next()?;

    let (kind, number, value) = if let Some(cc) = msg.strip_prefix("CC") {
        let (num, val) = cc.split_once('=')?;
        ("cc", midi_byte(num)?, Some(midi_byte(val)?))
    } else if let Some(note) = msg.strip_prefix("NoteOn") {
        let vel = tokens.next().and_then(|t| t.strip_prefix("vel")).and_then(midi_byte);
        ("note", midi_byte(note)?, vel)
    } else if let Some(note) = msg.strip_prefix("NoteOff") {
        ("note", midi_byte(note)?, None)
    } else if let Some(program) = msg.strip_prefix("PC") {
        ("pc", midi_byte(program)?, None)
    } else {
        return None;
    };

    Some(LearnedMidi {
        kind,
        channel: channel - 1,
        number,
        value,
        source: source.to_string(),
    })
}

/// Read console output until a `[MIDI RX ...]` line arrives (`Some`), `cancel`
/// is set (`None`), or `timeout` elapses (error).
fn read_learned<R: Read + ?Sized>(
    src: &mut R,
    timeout: Duration,
    cancel: &AtomicBool,
) -> Result<Option<LearnedMidi>, ConfigError> {
    let deadline = Instant::now() + timeout;
    // Bytes, not text: a read can split a multi-byte button label, and lines
    // are only decoded once complete.
    let mut pending: Vec<u8> = Vec::new();
    let mut buf = [0u8; 256];

    while Instant::now() < deadline {
        if cancel.load(Ordering::SeqCst) {
            return Ok(None);
        }
        match src.read(&mut buf) {
            Ok(0) => std::thread::sleep(Duration::from_millis(10)),
            Ok(n) => {
                pending.extend_from_slice(&buf[..n]);
                while let Some(pos) = pending.iter().position(|&b| b == b'\n') {
                    let line: Vec<u8> = pending.drain(..=pos).collect();
                    if let Some(msg) = parse_rx_line(&String::from_utf8_lossy(&line)) {
                        return Ok(Some(msg));
                    }
                }
                // A newline-free flood (e.g. a binary glitch) can't hold a line
                // we want; don't let it grow without bound.
                if pending.len() > 4096 {
                    pending.clear();
                }
            }
            Err(e)
                if e.kind() == std::io::ErrorKind::TimedOut
                    || e.kind() == std::io::ErrorKind::Interrupted => {}
            Err(e) => {
                return Err(ConfigError::msg(format!("Lost the device's serial connection: {e}")))
            }
        }
    }
    Err(ConfigError::msg(format!(
        "No MIDI received in {} seconds. Send a CC, Note or Program Change to the pedal, \
         and check that MIDI Routing passes USB/DIN → This pedal.",
        timeout.as_secs()
    )))
}

/// Wait for the next MIDI message the device receives and return it.
/// Resolves `None` when cancelled via `cancel_midi_learn`.
#[command]
pub async fn learn_midi(path: String) -> Result<Option<LearnedMidi>, ConfigError> {
    validate_device_path(&path)?;
    let path = PathBuf::from(path);
    verify_device_connected(&path)?;
    LEARN_CANCEL.store(false, Ordering::SeqCst);

    // Serial reads block; keep them off the IPC thread.
    tauri::async_runtime::spawn_blocking(move || {
        let mut port = open_device_serial(&path)?;
        // Short reads so cancel is noticed promptly.
        let _ = port.set_timeout(Duration::from_millis(100));
        // Only a message sent after Learn was clicked should count, not
        // console output already sitting in the OS buffer.
        let _ = port.clear(serialport::ClearBuffer::Input);
        read_learned(&mut *port, LEARN_TIMEOUT, &LEARN_CANCEL)
    })
    .await
    .map_err(|e| ConfigError::msg(format!("MIDI Learn task panicked: {e}")))?
}

#[command]
pub fn cancel_midi_learn() {
    LEARN_CANCEL.store(true, Ordering::SeqCst);
}

#[cfg(test)]
mod tests {
    use super::*;

    fn learned(kind: &'static str, channel: u8, number: u8, value: Option<u8>, source: &str) -> LearnedMidi {
        LearnedMidi { kind, channel, number, value, source: source.to_string() }
    }

    #[test]
    fn parses_every_firmware_rx_format() {
        assert_eq!(parse_rx_line("[MIDI RX USB] Ch1 CC20=127\r\n"), Some(learned("cc", 0, 20, Some(127), "USB")));
        assert_eq!(parse_rx_line("[MIDI RX DIN] Ch16 NoteOn60 vel100"), Some(learned("note", 15, 60, Some(100), "DIN")));
        assert_eq!(parse_rx_line("[MIDI RX USB] Ch3 NoteOff64"), Some(learned("note", 2, 64, None, "USB")));
        assert_eq!(parse_rx_line("[MIDI RX USB] Ch2 PC0"), Some(learned("pc", 1, 0, None, "USB")));
    }

    #[test]
    fn ignores_non_rx_and_malformed_lines() {
        for line in [
            "[MIDI TX] Ch1 CC20=127 (switch 1, toggle)",
            "[PAGE] CC20=1 -> page 1",
            "Button 1: Ch1 CC20 (TAP)",
            "[MIDI RX USB] Ch0 CC20=127",
            "[MIDI RX USB] Ch17 CC20=127",
            "[MIDI RX USB] Ch1 CC200=127",
            "[MIDI RX USB] Ch1 CC20",
            "[MIDI RX USB] Ch1 PitchBend42",
            "",
        ] {
            assert_eq!(parse_rx_line(line), None, "{line:?}");
        }
    }

    /// Hands out one chunk per read, then reports timeouts forever.
    struct ChunkedReader(Vec<Vec<u8>>);

    impl Read for ChunkedReader {
        fn read(&mut self, buf: &mut [u8]) -> std::io::Result<usize> {
            if self.0.is_empty() {
                return Err(std::io::Error::new(std::io::ErrorKind::TimedOut, "quiet"));
            }
            let chunk = self.0.remove(0);
            buf[..chunk.len()].copy_from_slice(&chunk);
            Ok(chunk.len())
        }
    }

    fn chunks(parts: &[&str]) -> ChunkedReader {
        ChunkedReader(parts.iter().map(|p| p.as_bytes().to_vec()).collect())
    }

    #[test]
    fn returns_first_rx_line_split_across_reads() {
        let mut r = chunks(&[
            "[MIDI TX] Ch1 CC20=127 (switch 1, toggle)\r\n[MIDI RX U",
            "SB] Ch5 CC7",
            "=64\r\n[MIDI RX USB] Ch1 PC3\r\n",
        ]);
        let got = read_learned(&mut r, Duration::from_secs(2), &AtomicBool::new(false)).unwrap();
        assert_eq!(got, Some(learned("cc", 4, 7, Some(64), "USB")));
    }

    #[test]
    fn survives_a_multibyte_char_split_across_reads() {
        let label = "[MIDI TX] Ch1 CC20=127 (switch 1, \u{25b2})\r\n".as_bytes();
        let split = label.len() - 5; // inside the 3-byte ▲
        let mut r = ChunkedReader(vec![
            label[..split].to_vec(),
            label[split..].to_vec(),
            b"[MIDI RX DIN] Ch1 NoteOn36 vel90\r\n".to_vec(),
        ]);
        let got = read_learned(&mut r, Duration::from_secs(2), &AtomicBool::new(false)).unwrap();
        assert_eq!(got, Some(learned("note", 0, 36, Some(90), "DIN")));
    }

    #[test]
    fn cancel_returns_none() {
        let mut r = chunks(&[]);
        let got = read_learned(&mut r, Duration::from_secs(2), &AtomicBool::new(true)).unwrap();
        assert_eq!(got, None);
    }

    #[test]
    fn times_out_with_an_error() {
        let mut r = chunks(&["[MIDI TX] Ch1 CC20=127 (switch 1, toggle)\r\n"]);
        let err = read_learned(&mut r, Duration::from_millis(200), &AtomicBool::new(false)).unwrap_err();
        assert!(err.message.contains("No MIDI received"), "{}", err.message);
    }
}
