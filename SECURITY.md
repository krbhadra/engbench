# Security

Please report problems privately through GitHub's **[Report a vulnerability](https://github.com/krbhadra/engbench/security/advisories/new)**, not in a public issue. In scope:

- A way to read or reconstruct the private held-out tasks or their answer keys.
- A way to get a design graded as a pass that is wrong, or to fake a submitted result so it survives `harness/regrade.py`.
- A way for model output to escape the agentic Python sandbox and reach the host running the harness.
- Secrets or personal data in the repository or its history.

Grader disagreements on engineering grounds (a defensible reading the grader rejects) are not security issues. Please open a normal issue for those (see [CONTRIBUTING.md](CONTRIBUTING.md)).
