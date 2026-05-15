mod parser;

use parser::parse_positive_i32;

fn assert_ok(actual: Result<i32, String>, expected: i32, message: &str) {
    match actual {
        Ok(value) if value == expected => {}
        Ok(value) => panic!("{}: expected {}, got {}", message, expected, value),
        Err(err) => panic!("{}: expected Ok({}), got Err({})", message, expected, err),
    }
}

fn assert_err(actual: Result<i32, String>, message: &str) {
    if actual.is_ok() {
        panic!("{}", message);
    }
}

fn main() {
    assert_ok(parse_positive_i32("42"), 42, "plain positive integer should parse");
    assert_ok(parse_positive_i32(" 7 "), 7, "surrounding whitespace should be accepted");
    assert_err(parse_positive_i32("0"), "zero should return Err");
    assert_err(parse_positive_i32("-3"), "negative numbers should return Err");
    assert_err(parse_positive_i32("not-a-number"), "invalid input should return Err");

    println!("OK");
}
