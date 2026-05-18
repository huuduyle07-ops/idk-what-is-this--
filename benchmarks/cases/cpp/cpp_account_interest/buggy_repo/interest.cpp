#include "interest.h"
#include <cmath>
#include <stdexcept>

double compute_compound_interest(double principal, double rate, int years) {
    // BUG: accepts negative principal, negative rate, and negative years.
    double final_amount = principal * std::pow(1.0 + rate, years);
    return final_amount - principal;
}
