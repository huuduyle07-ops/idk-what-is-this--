#include "processor.h"
#include <cstdlib>
#include <iostream>
#include <string_view>

static void assert_sv(std::string_view actual, std::string_view expected, const char* msg) {
    if (actual != expected) {
        std::cerr << "FAIL: " << msg
                  << ": expected '" << expected << "', got '" << actual << "'\n";
        std::exit(1);
    }
}

int main() {
    assert_sv(extract_bracket_content("[hello]"),          "hello", "simple bracketed word");
    assert_sv(extract_bracket_content("prefix[world]end"), "world", "embedded brackets");
    assert_sv(extract_bracket_content("[x]"),              "x",     "single char");
    assert_sv(extract_bracket_content("no brackets"),      "",      "no brackets");
    assert_sv(extract_bracket_content("["),                "",      "unclosed bracket");
    std::cout << "OK\n";
    return 0;
}
