# Install Facebook Marketplace Poster

This skill supplies instructions to a compatible agent; it is not a standalone application. To publish, your agent also needs access to a signed-in Facebook session and a browser computer-use tool that can upload local photos.

## Ask your agent to install it

Give Codex or Claude Code this request:

> Install Facebook Marketplace Poster from https://github.com/Mstormer/ai-tools-and-skills/tree/main/facebook-marketplace-poster by following its INSTALL.md.

## Install manually

1. On the [repository page](https://github.com/Mstormer/ai-tools-and-skills), choose **Code → Download ZIP** and extract it, or clone the repository.
2. Copy the entire `facebook-marketplace-poster` folder into the appropriate personal skills folder below. Create the parent folders if they do not exist.

   | Agent | macOS / Linux | Windows |
   |---|---|---|
   | Codex | `~/.agents/skills/facebook-marketplace-poster/` | `%USERPROFILE%\.agents\skills\facebook-marketplace-poster\` |
   | Claude Code | `~/.claude/skills/facebook-marketplace-poster/` | `%USERPROFILE%\.claude\skills\facebook-marketplace-poster\` |

   `~` means your home folder. If the agent runs inside WSL, use its Linux home folder. If a destination already exists, review it before replacing anything.
3. Confirm that `SKILL.md` is directly inside the copied `facebook-marketplace-poster` folder, alongside `agents/`.
4. Start a new conversation and ask: “Use Facebook Marketplace Poster to prepare a listing.” It should ask for your item folder if you haven't provided one. This check does not publish a listing.

For a single project instead of all projects, use `.agents/skills/` in the project for Codex or `.claude/skills/` for Claude Code. See the official [Codex skills guide](https://developers.openai.com/codex/skills) and [Claude Code skills guide](https://code.claude.com/docs/en/skills) for discovery details.

If the skill doesn't appear, check the folder layout and restart the agent. In Claude Code, `/reload-skills` can refresh newly created skills directories.
