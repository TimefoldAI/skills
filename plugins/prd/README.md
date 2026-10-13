# Timefold PRD

A plugin that helps you define the requirements of one optimization model, such as shift
scheduling, delivery routing or technician dispatch. Claude interviews you in the words of your
own business and writes a requirements document (PRD) for Timefold.

The plugin has two parts:

- **The Timefold PRD Chat connector** (`.mcp.json`): the MCP server that stores the interview and
  the PRD at Timefold. You sign in with your Timefold account the first time Claude uses it.
- **A requirements pane for Claude Code** (`hooks/`): a mod that shows the interview's checklist
  beside the conversation, as the PRD Chat website does. The pane shows the requirements coverage
  as a percentage and the interview's reference, such as `#PRD-3F9A2C`. Each topic shows its
  status (open, in progress or covered), and the topic Claude asks about now is marked. Unfold a
  topic to see what Claude captured. On a topic that is not covered, press **Talk about this** to
  make Claude ask about that topic next. **Download report** asks Claude to write the PRD and saves
  it in the session folder, with the same file name as the website gives it, such as
  `plan-van-routes-PRD-3F9A2C.md`. **Submit for build** shows the same confirmation in the pane as the
  PRD Chat website: "We send your requirements document, as Markdown and PDF, to our solutions
  team", with your sign-in email as the contact email. The confirmation does not wait for the question
  Claude asks now. When you select **Submit**, the pane sends the PRD to Timefold. If Claude has not
  saved the PRD since your last answer, Claude writes it first, and the pane then sends it. To use
  another contact email, ask Claude to submit for build with that email. In Claude chat and Cowork,
  ask Claude to submit for build: Claude asks you the same question first.

The pane shows in the Claude Code terminal and in the Code tab of the Claude desktop app. In
Claude on the web and in the desktop chat, the connector works without the pane.

## Install

In Claude Code:

```bash
claude plugin marketplace add TimefoldAI/skills
claude plugin install prd@timefold
```

Then ask Claude to "help me define the requirements for my delivery routing". The pane opens
when the interview starts, if the terminal is at least 144 columns wide. Run `/prd-panel` to
open it at any width.

## Permissions

The pane reads the interview's progress with one extra call to the connector, the read-only tool
`get_interview_progress`. The mod makes this call in the background after each interview step,
not Claude, so no conversation stands behind it. In auto mode, the permission classifier then
gives no verdict and refuses the call, and in the other modes you would get a permission prompt
after each step. When you confirm **Submit for build** in the pane, the mod also calls
`submit_for_build` itself, for the same reason.

So the mod approves these two calls itself, through a `tool.check` hook (see
[Extend permissions with hooks](https://code.claude.com/docs/en/permissions#extend-permissions-with-hooks)):

- It approves only a tool whose name ends in `__get_interview_progress`, or in
  `__submit_for_build`. The pane calls `submit_for_build` only after you select **Submit** in its
  confirmation, and that selection is your consent.
- It approves only the calls the mod itself makes (`next.origin.plugin` is this plugin). When
  Claude calls the same tool, the usual permission decision applies.
- It approves nothing else. Every other tool call goes to your rules, your hooks and your
  permission mode as before.

Both tools work only on your own interview: the connector refuses an interview that belongs to
another user. Deny rules from your organization's managed settings still hold over the mod.

To see what the mod hooks and calls before you install it, run
`claude plugin validate plugins/prd` in a clone of this repository.

## Develop

```bash
claude --plugin-dir plugins/prd   # load this folder for one session
claude plugin test plugins/prd    # run the mod's tests
```
