#include "filter.h"
#include <cstdlib>
#include <iostream>
#include <vector>

static void fail(const char* msg) {
    std::cerr << "FAIL: " << msg << "\n";
    std::exit(1);
}

int main() {
    // all negatives — buggy code skips alternating, leaves {-2}
    std::vector<int> v1 = {-3, -2, -1};
    int n1 = remove_negatives(v1);
    if (!v1.empty())   fail("all negatives: vector should be empty");
    if (n1 != 3)       fail("all negatives: should report 3 removed");

    // mixed
    std::vector<int> v2 = {-1, 2, -3, 4};
    int n2 = remove_negatives(v2);
    if (v2.size() != 2)               fail("mixed: two positives should remain");
    if (v2[0] != 2 || v2[1] != 4)    fail("mixed: positives should be 2 and 4");
    if (n2 != 2)                      fail("mixed: should report 2 removed");

    // no negatives
    std::vector<int> v3 = {1, 2, 3};
    int n3 = remove_negatives(v3);
    if (v3.size() != 3)  fail("no negatives: nothing should be removed");
    if (n3 != 0)         fail("no negatives: should report 0 removed");

    std::cout << "OK\n";
    return 0;
}
