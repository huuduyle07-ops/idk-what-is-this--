#include "interest.h"
#include <cmath>
#include <cstdlib>
#include <iostream>
#include <stdexcept>
#include <string>

static void assert_close(double actual, double expected, const std::string& message) {
    if (std::fabs(actual - expected) > 1e-6) {
        std::cerr << message << ": expected " << expected << ", got " << actual << "\n";
        std::exit(1);
    }
}

static void assert_throws(void (*fn)(), const std::string& message) {
    try {
        fn();
    } catch (const std::invalid_argument&) {
        return;
    } catch (...) {
        std::cerr << message << ": wrong exception type\n";
        std::exit(1);
    }
    std::cerr << message << ": no exception thrown\n";
    std::exit(1);
}

static void neg_principal()  { compute_compound_interest(-100.0, 0.05, 1); }
static void neg_rate()       { compute_compound_interest(100.0, -0.05, 1); }
static void neg_years()      { compute_compound_interest(100.0, 0.05, -1); }

int main() {
    assert_close(compute_compound_interest(1000.0, 0.05, 1), 50.0,
                 "1 year at 5% on 1000 should give 50");
    assert_close(compute_compound_interest(1000.0, 0.10, 2), 210.0,
                 "2 years at 10% on 1000 should give 210");
    assert_close(compute_compound_interest(0.0, 0.05, 10), 0.0,
                 "zero principal should give 0");
    assert_close(compute_compound_interest(1000.0, 0.0, 10), 0.0,
                 "zero rate should give 0");
    assert_close(compute_compound_interest(1000.0, 0.05, 0), 0.0,
                 "zero years should give 0");

    assert_throws(neg_principal, "negative principal should throw");
    assert_throws(neg_rate, "negative rate should throw");
    assert_throws(neg_years, "negative years should throw");

    std::cout << "OK\n";
    return 0;
}
