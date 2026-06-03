mod path_guard;
use path_guard::safe_resolve;
use std::path::Path;

fn main() {
    let base = Path::new("files");

    // safe path should resolve and remain under base
    let r = safe_resolve(base, "readme.txt");
    assert!(r.is_some(), "safe path: expected Some, got None");
    assert!(r.unwrap().starts_with(base), "safe path: must be under base");

    // direct traversal must be rejected
    let r = safe_resolve(base, "../secret.txt");
    assert!(r.is_none(), "traversal '../secret.txt': expected None");

    // nested traversal that escapes base must be rejected
    let r = safe_resolve(base, "sub/../../etc/passwd");
    assert!(r.is_none(), "traversal 'sub/../../etc/passwd': expected None");

    // subdirectory should resolve
    let r = safe_resolve(base, "sub/data.txt");
    assert!(r.is_some(), "subdirectory path: expected Some, got None");
    assert!(r.unwrap().starts_with(base), "subdirectory path: must be under base");

    println!("OK");
}
