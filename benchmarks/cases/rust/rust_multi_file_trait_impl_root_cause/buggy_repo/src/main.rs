mod processor;
use processor::{Document, Summarize};

fn check_eq(actual: usize, expected: usize, label: &str) {
    if actual != expected {
        panic!("{}: expected {}, got {}", label, expected, actual);
    }
}

fn main() {
    let doc = Document { content: String::from("hello world foo") };
    check_eq(doc.word_count(), 3, "three words");

    let single = Document { content: String::from("one") };
    check_eq(single.word_count(), 1, "single word");

    let empty = Document { content: String::new() };
    check_eq(empty.word_count(), 0, "empty document");

    let padded = Document { content: String::from("  spaced   out  ") };
    check_eq(padded.word_count(), 2, "extra whitespace ignored");

    println!("OK");
}
