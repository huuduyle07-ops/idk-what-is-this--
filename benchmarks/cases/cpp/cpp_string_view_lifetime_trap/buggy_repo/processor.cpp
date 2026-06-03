#include "processor.h"

std::string_view extract_bracket_content(std::string_view input) {
    std::size_t open  = input.find('[');
    std::size_t close = input.rfind(']');
    if (open  == std::string_view::npos ||
        close == std::string_view::npos ||
        close <= open) {
        return {};
    }
    // BUG: off-by-one — includes '[' in result and misses last char before ']'
    return input.substr(open, close - open);
}
