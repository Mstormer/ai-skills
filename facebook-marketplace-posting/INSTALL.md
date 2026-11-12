# Install Facebook Marketplace Poster

This skill supplies instructions to a compatible agent; it is not a standalone application. To research prices and post, your agent also needs a signed-in Facebook session in Chrome and a browser-control tool that can upload local photos.

## Ask your agent to install it

Give Claude Code or Codex this request:

> Install Facebook Marketplace Poster from https://github.com/Mstormer/ai-skills/tree/main/facebook-marketplace-posting by following its INSTALL.md.

## Install manually

1. On the [repository page](https://github.com/Mstormer/ai-skills), choose **Code → Download ZIP** and extract it, or clone the repository.
2. Copy the entire `facebook-marketplace-posting` folder into the appropriate personal skills folder below. Create the parent folders if they do not exist.

   | Agent | macOS / Linux | Windows |
   |---|---|---|
   | Claude Code | `~/.claude/skills/facebook-marketplace-posting/` | `%USERPROFILE%\.claude\skills\facebook-marketplace-posting\` |
   | Codex | `~/.agents/skills/facebook-marketplace-posting/` | `%USERPROFILE%\.agents\skills\facebook-marketplace-posting\` |

   `~` means your home folder. If the agent runs inside WSL, use its Linux home folder. If a destination already exists, review it before replacing anything.
3. Confirm that `SKILL.md` is directly inside the copied `facebook-marketplace-posting` folder, alongside `references/` and `agents/`.
4. Start a new conversation and ask: "Use Facebook Marketplace Poster to price my items." It should ask for your inventory folder if you haven't provided one. This check does not publish anything.

### Upgrading from Facebook Marketplace Poster v1

The earlier version was installed as `facebook-marketplace-poster`. Remove or move that folder out of your skills folder after installing this one, so the agent doesn't see two versions.

For a single project instead of all projects, use `.claude/skills/` in the project for Claude Code or `.agents/skills/` for Codex. See the official [Claude Code skills guide](https://code.claude.com/docs/en/skills) and [Codex skills guide](https://developers.openai.com/codex/skills) for discovery details.

If the skill doesn't appear, check the folder layout and restart the agent.
