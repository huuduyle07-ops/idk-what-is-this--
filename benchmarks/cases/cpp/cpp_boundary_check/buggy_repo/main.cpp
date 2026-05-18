#include "bounds.h"

#include <iostream>
#include <stdexcept>
#include <string>

void require(bool condition, const std::string& message) {
    if (!condition) {
        throw std::runtime_error(message);
    }
}

int main() {
    require(is_in_bounds(0, 0, 5, 3), "origin should be inside");
    require(is_in_bounds(4, 2, 5, 3), "last valid cell should be inside");
    require(!is_in_bounds(-1, 0, 5, 3), "negative row should be outside");
    require(!is_in_bounds(0, -1, 5, 3), "negative column should be outside");
    require(!is_in_bounds(5, 2, 5, 3), "row equal to height should be outside");
    require(!is_in_bounds(4, 3, 5, 3), "column equal to width should be outside");

    std::cout << "OK\n";
    return 0;
}
