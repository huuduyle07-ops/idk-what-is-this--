pub fn parse_positive_i32(text: &str) -> Result<i32, String> {
    // BUG: invalid integers panic instead of returning Result::Err.
    let value = text.trim().parse::<i32>().unwrap();
    if value <= 0 {
        return Err("value must be positive".to_string());
    }
    Ok(value)
}
