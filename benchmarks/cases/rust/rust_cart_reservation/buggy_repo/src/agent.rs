use crate::cart::Cart;
use crate::inventory::Inventory;

pub fn reserve_item(
    inventory: &mut Inventory,
    cart: &mut Cart,
    item_id: &str,
    quantity: i32,
) -> Result<(), String> {
    let item = inventory
        .find_mut(item_id)
        .ok_or("item not found".to_string())?;

    // BUG: this allows zero/negative quantity and overdraft stock.
    item.stock -= quantity;
    cart.add(item_id, quantity);

    Ok(())
}
