# skills

Personal agent skills (one directory per skill, each with a `SKILL.md`).

## Install

### This machine, from a clone (recommended for editing)

```bash
git clone https://github.com/mfmezger/skills.git ~/coding/github/skills
~/coding/github/skills/install.sh            # --dry-run to preview
```

`install.sh` symlinks every skill into `~/.agents/skills` (read by pi, DSH and other
Agent Skills clients) and into `~/.claude/skills` when Claude Code is installed. Because the
installed skills are links, edits land directly in this repo — commit and push them from here.

- Re-run it after adding or removing skills; links to deleted skills are pruned.
- A local copy that differs from the repo is skipped (exit 1) so edits are never lost.
  Compare it with the printed `diff` command, or pass `--force` to move it to
  `~/.agents/skills-backup/<timestamp>/` and link anyway.

### Anywhere else, without a clone

```bash
npx skills add mfmezger/skills -g -a pi -a claude-code -y   # all skills
npx skills add mfmezger/skills -g -s commit -y              # a single skill
npx skills update -g                                        # pull new versions
```

This installs **copies** into `~/.agents/skills`. Don't edit them in place: `npx skills update`
does not notice local changes, so they silently drift from the repo.
