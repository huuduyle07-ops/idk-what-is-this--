#include "filter.h"
#include <cstddef>

int remove_negatives(std::vector<int>& v) {
    // BUG: increments i after erase(), skipping the element that shifted into position i
    int removed = 0;
    for (std::size_t i = 0; i < v.size(); ++i) {
        if (v[i] < 0) {
            v.erase(v.begin() + static_cast<std::ptrdiff_t>(i));
            ++removed;
        }
    }
    return removed;
}
