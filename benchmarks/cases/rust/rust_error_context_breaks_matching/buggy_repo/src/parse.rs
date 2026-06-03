#[derive(Debug, PartialEq)]
pub enum ParseError {
    Empty,
    Invalid,
}

pub fn parse_field(s: &str) -> Result<i32, ParseError> {
    // BUG: maps all parse failures to ParseError::Invalid,
    // but empty/whitespace-only input should return ParseError::Empty
    s.trim()
        .parse::<i32>()
        .map_err(|_| ParseError::Invalid)
}
