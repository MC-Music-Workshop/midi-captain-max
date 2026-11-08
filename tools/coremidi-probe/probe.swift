// Minimal CoreMIDI sender: one MIDI client for the whole run, CC 100 on Ch 1
// alternating 1/0 to the named destination, `count` times, `gap` seconds apart.
// count=1 run once per message mimics one `sendmidi` call per message.
// Destination "-": only create the client and port, then exit (no destination
// needed, so nothing else has to hold a MIDI client open).
//
// Usage: probe <destination name|-> <count> <gap seconds>
// Prints one line per failure; exit status 1 if any send failed.
import CoreMIDI
import Foundation

let args = CommandLine.arguments
guard args.count == 4, let count = Int(args[2]), let gap = Double(args[3]) else {
  print("usage: probe <destination name> <count> <gap seconds>")
  exit(2)
}
let name = args[1]

func destination(named n: String) -> MIDIEndpointRef? {
  for i in 0..<MIDIGetNumberOfDestinations() {
    let d = MIDIGetDestination(i)
    var cf: Unmanaged<CFString>?
    if MIDIObjectGetStringProperty(d, kMIDIPropertyDisplayName, &cf) == noErr,
       let s = cf?.takeRetainedValue() as String?, s == n { return d }
  }
  return nil
}

var client = MIDIClientRef(), port = MIDIPortRef()
var st = MIDIClientCreateWithBlock("coremidi-probe" as CFString, &client, nil)
if st != noErr { print("MIDIClientCreate failed \(st)"); exit(1) }
st = MIDIOutputPortCreate(client, "out" as CFString, &port)
if st != noErr { print("MIDIOutputPortCreate failed \(st)"); exit(1) }
if name == "-" { exit(0) }

var fails = 0
for i in 1...count {
  guard let dest = destination(named: name) else {
    print("send \(i): destination '\(name)' not found")
    fails += 1
    continue
  }
  var list = MIDIPacketList()
  let pkt = MIDIPacketListInit(&list)
  let bytes: [UInt8] = [0xB0, 100, UInt8(i % 2)]
  _ = MIDIPacketListAdd(&list, 1024, pkt, 0, 3, bytes)
  st = MIDISend(port, dest, &list)
  if st != noErr { print("send \(i): MIDISend failed \(st)"); fails += 1 }
  if i < count { Thread.sleep(forTimeInterval: gap) }
}
exit(fails > 0 ? 1 : 0)
