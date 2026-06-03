mod parse;
use parse::{parse_field, ParseError};

fn main() {
    // valid integer
    match parse_field("42") {
        Ok(42) => {}
        other => panic!("valid integer: expected Ok(42), got {:?}", other),
    }

    // empty string must return Empty variant, not Invalid
    match parse_field("") {
        Err(ParseError::Empty) => {}
        other => panic!("empty string: expected Err(Empty), got {:?}", other),
    }

    // whitespace-only must return Empty variant
    match parse_field("   ") {
        Err(ParseError::Empty) => {}
        other => panic!("whitespace: expected Err(Empty), got {:?}", other),
    }

    // non-numeric must return Invalid
    match parse_field("abc") {
        Err(ParseError::Invalid) => {}
        other => panic!("non-numeric: expected Err(Invalid), got {:?}", other),
    }

    println!("OK");
}
