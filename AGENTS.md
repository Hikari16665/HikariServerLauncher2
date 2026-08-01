# Repository rules

- After completing any materially meaningful software change, verify the affected area and create a Git commit before reporting completion.
- Keep each commit scoped to one coherent completed change. Do not include unrelated user work in a commit.
- The frontend About page build identifier must come from the Git commit being built. Keep the Vite build-time `git rev-parse HEAD` injection working; do not replace it with a manually maintained value or `TODO`.
- If a requested change cannot be committed safely because unrelated edits overlap the same files, stop and explain the conflict instead of committing unknown work.
