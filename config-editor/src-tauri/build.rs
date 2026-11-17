fn main() {
    // updates.rs reads the release version with option_env!; rebuild when CI sets it.
    println!("cargo:rerun-if-env-changed=MCM_VERSION");
    tauri_build::build()
}
