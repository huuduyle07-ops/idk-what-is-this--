#[derive(Clone, Debug)]
pub struct CartLine {
    pub item_id: String,
    pub quantity: i32,
}

pub struct Cart {
    lines: Vec<CartLine>,
}

impl Cart {
    pub fn new() -> Self {
        Self { lines: Vec::new() }
    }

    pub fn add(&mut self, item_id: &str, quantity: i32) {
        if let Some(line) = self.lines.iter_mut().find(|line| line.item_id == item_id) {
            line.quantity += quantity;
        } else {
            self.lines.push(CartLine {
                item_id: item_id.to_string(),
                quantity,
            });
        }
    }

    pub fn quantity_of(&self, item_id: &str) -> i32 {
        self.lines
            .iter()
            .find(|line| line.item_id == item_id)
            .map(|line| line.quantity)
            .unwrap_or(0)
    }
}
