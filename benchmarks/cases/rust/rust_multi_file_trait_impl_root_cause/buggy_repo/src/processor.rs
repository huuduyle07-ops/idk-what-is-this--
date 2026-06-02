pub trait Summarize {
    fn word_count(&self) -> usize;
}

pub struct Document {
    pub content: String,
}

impl Summarize for Document {
    fn word_count(&self) -> usize {
        // BUG: counts bytes/characters instead of whitespace-delimited words
        self.content.len()
    }
}
