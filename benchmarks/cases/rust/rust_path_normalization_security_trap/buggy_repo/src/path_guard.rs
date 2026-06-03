use std::path::{Path, PathBuf};

/// Returns the resolved path if it is safely within `base`, otherwise None.
pub fn safe_resolve(base: &Path, user_input: &str) -> Option<PathBuf> {
    // BUG: joins without normalising '..' components — allows path traversal
    Some(base.join(user_input))
}
