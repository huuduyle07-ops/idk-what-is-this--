mod inventory;
mod cart;
mod agent;

use inventory::{Inventory, Item};
use cart::Cart;

fn main() {
    let mut inventory = Inventory::new();
    let mut cart = Cart::new();

    inventory.insert(Item {
        id: "book".to_string(),
        stock: 5,
    });

    let result = agent::reserve_item(&mut inventory, &mut cart, "book", 2);
    if result.is_err() {
        panic!("valid reservation should pass");
    }

    if inventory.find("book").unwrap().stock != 3 {
        panic!("valid reservation should decrease stock");
    }

    if cart.quantity_of("book") != 2 {
        panic!("valid reservation should increase cart quantity");
    }

    if agent::reserve_item(&mut inventory, &mut cart, "book", 10).is_ok() {
        panic!("insufficient stock should fail");
    }

    if agent::reserve_item(&mut inventory, &mut cart, "book", 0).is_ok() {
        panic!("zero quantity should fail");
    }

    if agent::reserve_item(&mut inventory, &mut cart, "missing", 1).is_ok() {
        panic!("missing item should fail");
    }

    if inventory.find("book").unwrap().stock != 3 {
        panic!("failed reservations must not change stock");
    }

    if cart.quantity_of("book") != 2 {
        panic!("failed reservations must not change cart quantity");
    }

    println!("OK");
}
