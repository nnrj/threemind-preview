use std::{env, fs, path::PathBuf};

fn main() {
    println!("cargo:rerun-if-env-changed=THREEMIND_KERNEL_DEFINITION");
    let data = match env::var_os("THREEMIND_KERNEL_DEFINITION") {
        Some(path) => {
            let path = PathBuf::from(path);
            println!("cargo:rerun-if-changed={}", path.display());
            let bytes = fs::read(path).expect("cannot read embedded kernel definition");
            assert!(bytes.len() <= 1_048_576, "kernel definition too large");
            bytes
        }
        None => b"null".to_vec(),
    };
    fs::write(
        PathBuf::from(env::var_os("OUT_DIR").unwrap()).join("kernel-definition.json"),
        data,
    )
    .unwrap();
}
