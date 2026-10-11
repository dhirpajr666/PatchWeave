# Review webhooks sketch

The queue already ranks by severity. A webhook could emit one payload per
band crossing so reviewers hear about unanchored edits before the next poll.

Open questions: retry policy, and whether the payload mirrors the brief or
just references it. Both keep the brief format untouched.
