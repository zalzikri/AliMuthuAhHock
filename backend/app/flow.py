"""The real GT onboarding sequence.

Two axes decide what a hire needs:
  employment : staff | intern        -> GEMS, GES, GSD
  job_family : developer | other     -> Bitbucket, GCP, repo

Four channels decide how each request is made:
  gsd_auto      Day One raises a Freshservice ticket and polls its status.
  slack_guided  Day One cannot post to Slack. It writes the message; the hire sends it.
  self          The hire does it.
  person        A named person acts directly. No ticket exists for this.

Source: Zal (GT developer) and gtech-docs/apps/docs/platform/requests/index.md.
"""
from dataclasses import dataclass

GSD_AUTO, SLACK_GUIDED, SELF, PERSON = "gsd_auto", "slack_guided", "self", "person"


@dataclass(frozen=True)
class Step:
    id: str
    title: str
    system: str
    channel: str
    eta_days: int
    deps: tuple = ()
    deps_intern: tuple | None = None
    staff_only: bool = False
    developer_only: bool = False
    needs_project: bool = False
    optional: bool = False
    subject: str = ""
    body: str = ""
    ask: str = ""          # the short message Day One writes, for a `person` step
    fields: tuple = ()     # pre-filled form values, for a `slack_guided` step
    howto: tuple = ()      # numbered instructions shown on the card
    then_self: bool = False  # IT grants it, then the hire still has to sign in
    self_after: tuple = ()   # her own part waits for these, e.g. she needs her inbox first
    hint: str = ""         # one line of context shown on the card


# Stages run strictly in order: a stage's requests go out only when the stage before it is
# fully done, including her own confirmations. Then nothing finishes "ahead" of her, and the
# stepper always matches the list. This is also GT's real order: sign in, then HR systems and
# GSD, then Slack / Atlassian / Bitbucket, then the project. Skipped steps (interns) are
# ignored by the engine. The optional Claude seat does not hold up the project stage.
HR_STAGE = ("gems", "ges", "gsd")
TOOLS_STAGE = ("slack", "atlassian", "bitbucket")

STEPS: tuple[Step, ...] = (
    Step("email", "Google Workspace email", "Google Workspace", GSD_AUTO, 3,
         subject="New email account for {name}",
         body="Create a Google Workspace account for {name} ({employment}), "
              "starting {start_date}{project_clause}.\n\n"
              "Please reply on this ticket with the created address, so the "
              "remaining access requests can go out automatically."),

    # Google generates a temporary password and mails the sign-in details to the
    # requester, so the starter holds it - not the new hire. She cannot do this alone.
    Step("password_reset", "Sign in and set your password", "Google Workspace", SELF, 0,
         deps=("email",),
         hint="IT made your account. Do these 3 steps. They take about 2 minutes.",
         howto=(
             "Ask {starter} to send you the welcome email from Google. Google sent it "
             "to them, because they started your onboarding.",
             "Click the sign-in link in that email. Set your own password. "
             "Your sign-in name is {work_email}.",
             "The link works for 48 hours only. If it stops working, IT must reset "
             "your account.",
         )),

    Step("gems", "GEMS", "SAP SuccessFactors", GSD_AUTO, 3,
         deps=("password_reset",), staff_only=True,
         subject="GEMS access for {name}",
         body="Grant GEMS access for {name}. Login is the Google Workspace email."),

    # GES mails the WORK address with a user ID and a temporary password, so this
    # one she can finish alone - unlike the Google sign-in.
    Step("ges", "GES", "GES", GSD_AUTO, 3,
         deps=("password_reset",), staff_only=True,
         subject="GES access for {name}",
         body="Grant GES access for {name}. Login is the employee ID.",
         then_self=True, self_after=("password_reset",),
         hint="GES shows your role, employee details, KPI and leave.",
         howto=(
             "GES sends your user ID and a temporary password to {work_email}. "
             "Look in that inbox, not in your personal email.",
             "Your user ID is the employee ID on your employee card.",
             "Sign in. When GES asks, set your own password.",
         )),

    Step("gsd", "GSD portal access", "Freshservice", GSD_AUTO, 3,
         deps=("password_reset",), staff_only=True,
         subject="GSD portal access for {name}",
         body="Grant GSD requester access so {name} can raise their own tickets."),

    Step("slack", "Slack", "Slack", GSD_AUTO, 3,
         deps=HR_STAGE, deps_intern=("password_reset",),
         subject="Slack access for {name}",
         body="Add {name} to gamudatechnologies.slack.com."),

    Step("atlassian", "Atlassian", "Atlassian", GSD_AUTO, 3,
         deps=HR_STAGE, deps_intern=("password_reset",),
         subject="Atlassian access for {name}",
         body="Grant Jira and Confluence access for {name}."),

    Step("bitbucket", "Bitbucket account", "Bitbucket", GSD_AUTO, 3,
         deps=HR_STAGE, deps_intern=("password_reset",), developer_only=True,
         subject="Bitbucket access for {name}",
         body="Grant Bitbucket access for {name}."),

    # /gcp-request is a Slack command, so Slack must exist first.
    # /gcp-request opens a modal in Slack. There is no message to send, so Day One
    # fills the modal's fields instead. Field names from
    # gtech-docs/apps/docs/platform/requests/gcp-access.md.
    Step("gcp", "GCP project access", "GCP", SLACK_GUIDED, 2,
         deps=TOOLS_STAGE, developer_only=True,
         hint="You request GCP access in Slack, not in GSD. Type /gcp-request in Slack. "
              "A form opens. Copy these values into it.",
         fields=(
             ("What do you need?",
              "Grant roles/viewer to {work_email} on {gcp_project}"),
             ("Action Type", "Grant access"),
             ("GCP Project ID", "{gcp_project}"),
             ("Resource / Service", "IAM"),
             ("What is this for?",
              "New {job_title} joining {project} on {start_date}. Needs roles/viewer on dev "
              "to read resources and logs, and roles/editor on non-production for daily work. "
              "Team: {project}."),
             ("Urgency", "Medium"),
             ("Deadline", "leave blank"),
         )),

    # The repo admin adds you directly. There is no ticket for this.
    Step("repo_access", "Added to the repo", "Bitbucket", PERSON, 1,
         deps=TOOLS_STAGE, developer_only=True, needs_project=True,
         hint="{poc_name} adds you to the repo in Bitbucket. There is no GSD ticket for this. "
              "Send this message to {poc_name}.",
         ask="Hi {poc_first}, please add {work_email} to {repo}. "
             "I joined {project} on {start_date}. Thank you."),

    Step("claude_seat", "Claude Code seat", "Freshservice", GSD_AUTO, 3,
         deps=HR_STAGE, deps_intern=("password_reset",), optional=True,
         subject="Claude Code seat for {name}",
         body="Assign a Claude Code licence seat to {name}."),
)

STEP_BY_ID = {s.id: s for s in STEPS}


def plan(employment: str = "staff", job_family: str = "developer",
         project: str | None = None, want_claude: bool = True) -> list[Step]:
    intern = employment == "intern"
    developer = job_family == "developer"
    out = []
    for s in STEPS:
        if s.staff_only and intern:
            continue
        if s.developer_only and not developer:
            continue
        if s.needs_project and not project:
            continue
        if s.optional and not want_claude:
            continue
        out.append(s)
    return out


def deps_for(step: Step, employment: str) -> tuple:
    if employment == "intern" and step.deps_intern is not None:
        return step.deps_intern
    return step.deps


def skipped(employment: str, job_family: str, project: str | None) -> list[tuple[str, str]]:
    """What this hire does NOT get, and why. Shown struck through on the form."""
    intern = employment == "intern"
    developer = job_family == "developer"
    out = []
    for s in STEPS:
        if s.staff_only and intern:
            out.append((s.title, "not for interns"))
        elif s.developer_only and not developer:
            out.append((s.title, "for developers only"))
        elif s.needs_project and not project:
            out.append((s.title, "needs a project"))
    return out
