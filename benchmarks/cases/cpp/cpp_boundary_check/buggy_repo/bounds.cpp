#include "bounds.h"

bool is_in_bounds(int row, int col, int height, int width) {
    // BUG: row == height and col == width are outside the grid.
    return row >= 0 && col >= 0 && row <= height && col <= width;
}
