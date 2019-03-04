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
            current_churn_ = 0;
        } else if (starts_with(line, "--- ")) {
            // old-file header: ignored for churn accounting
            return;
        } else if (starts_with(line, "@@")) {
            ++hunks_;
        } else if (!line.empty() && line[0] == '+') {
            ++added_;
            ++current_churn_;
        } else if (!line.empty() && line[0] == '-') {
            ++removed_;
            ++current_churn_;
        }
    }

    void finish() { flush_file(); }

    void emit(std::ostream& out) const {
        out << "files=" << files_ << '\n';
        out << "added=" << added_ << '\n';
        out << "removed=" << removed_ << '\n';
        out << "hunks=" << hunks_ << '\n';
        out << "largest_file=" << largest_file_ << '\n';
        out << "largest_churn=" << largest_churn_ << '\n';
    }

private:
    static bool starts_with(const std::string& s, const char* prefix) {
        const std::string p(prefix);
        return s.size() >= p.size() && s.compare(0, p.size(), p) == 0;
    }

    static std::string trim(const std::string& s) {
        std::size_t begin = 0;
        std::size_t end = s.size();
        while (begin < end && is_space(s[begin])) ++begin;
        while (end > begin && is_space(s[end - 1])) --end;
        return s.substr(begin, end - begin);
    }

    static bool is_space(char c) {
        return c == ' ' || c == '\t' || c == '\r' || c == '\n';
    }

    void flush_file() {
        if (!current_file_.empty() && current_churn_ > largest_churn_) {
            largest_churn_ = current_churn_;
            largest_file_ = current_file_;
        }
    }

    std::uint64_t files_ = 0;
    std::uint64_t added_ = 0;
    std::uint64_t removed_ = 0;
    std::uint64_t hunks_ = 0;
    std::uint64_t current_churn_ = 0;
    std::uint64_t largest_churn_ = 0;
    std::string current_file_;
    std::string largest_file_;
};

}  // namespace patchweave

int main() {
    std::ios::sync_with_stdio(false);
    patchweave::MetricAccumulator acc;
    std::string line;
    while (std::getline(std::cin, line)) {
        acc.feed(line);
    }
    acc.finish();
    acc.emit(std::cout);
