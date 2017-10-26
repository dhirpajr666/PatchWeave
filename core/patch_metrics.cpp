// patch_metrics.cpp — PatchWeave native diff metric engine.
//
// A dependency-free, portable C++17 filter. It reads a unified-diff-style body
// from standard input and emits a set of `key=value` metric lines on standard
// output, which the Python bridge (patchweave/native.py) parses.
//
// Grammar recognised (lenient — unknown lines are ignored):
//   "+++ <path>"   opens a new file, resets its per-file churn counter
//   "--- <path>"   old-file header, ignored for counting
//   "@@ ... @@"    opens a hunk
//   "+<text>"      an added line (excluding the "+++" header)
//   "-<text>"      a removed line (excluding the "---" header)
//
// Output keys: files, added, removed, hunks, largest_file, largest_churn.
//
// Build (syntax-only):
//   g++ -std=c++17 -Wall -Wextra -pedantic -fsyntax-only core/patch_metrics.cpp
// Build (binary):
//   g++ -std=c++17 -O2 -o core/patch_metrics.bin core/patch_metrics.cpp

#include <iostream>
#include <string>
#include <cstdint>

namespace patchweave {

// Accumulates diff statistics as lines are fed in one at a time.
class MetricAccumulator {
public:
    void feed(const std::string& line) {
        if (starts_with(line, "+++ ")) {
            flush_file();
            ++files_;
            current_file_ = trim(line.substr(4));
