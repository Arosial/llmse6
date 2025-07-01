from typing import Optional

import git

from arox.agent_patterns.llm_base import LLMBaseAgent


class GitCommitAgent(LLMBaseAgent):
    """
    An agent that generates commit messages based on git diff output.
    """

    def __init__(self, name: str, config_parser=None, local_tool_manager=None):
        super().__init__(name, config_parser, local_tool_manager)

    async def generate_commit_message(self, diff: Optional[str] = None) -> str:
        """
        Generate a commit message based on the provided git diff or the current changes.

        Args:
            diff: Optional git diff string. If None, the current changes are fetched.

        Returns:
            str: The generated commit message.
        """
        if diff is None:
            # Fetch the current changes using git diff
            try:
                repo = git.Repo(search_parent_directories=True)
                diff = repo.git.diff("--staged")
            except git.InvalidGitRepositoryError:
                return "Error: Not a git repository"
            except git.GitCommandError as e:
                return f"Error fetching git diff: {e}"

        if not diff:
            return "No changes detected to generate a commit message."

        # Use the LLM to generate a commit message based on the diff
        prompt = (
            "Generate ONE concise and meaningful commit message based on the following git diff. "
            "Respond with ONLY commit message.\n\n"
            f"{diff}"
        )

        # Call the LLM to generate the commit message
        await self.llm_node(prompt)
        last_message = self.state.messages[-1]["content"]
        return last_message.strip()

    async def commit_changes(
        self, message: Optional[str] = None, co_author: Optional[str] = None
    ) -> str:
        """
        Commit the staged changes with the provided or generated commit message.

        Args:
            message: Optional commit message. If None, a message is generated.
            co_author: Optional co-author to include in the commit message.
                      If provided, the commit message will include:
                      "Co-authored-by: {co_author}"

        Returns:
            str: The output of the git commit command or an error message.
        """
        if message is None:
            message = await self.generate_commit_message()

        try:
            repo = git.Repo(search_parent_directories=True)

            if co_author:
                message = f"{message}\n\nCo-authored-by: {co_author}"
                commit = repo.index.commit(message)
            else:
                commit = repo.index.commit(message)

            return f"Committed {commit.hexsha}"
        except git.InvalidGitRepositoryError:
            return "Error: Not a git repository"
        except git.GitCommandError as e:
            return f"Error committing changes: {e}"

    async def auto_commit_changes(self, co_author: Optional[str] = None) -> str:
        """
        Automatically commit any uncommitted changes with a generated commit message.
        This includes both staged and unstaged changes.

        Returns:
            str: The output of the git commit command or an error message.
        """
        try:
            repo = git.Repo(search_parent_directories=True)

            # Stage all unstaged changes
            repo.git.add(".")

            # Check for staged changes
            diff = repo.git.diff("--staged")
            if not diff:
                return "No changes detected to commit."

            # Generate and commit the changes
            message = await self.generate_commit_message(diff)
            return await self.commit_changes(message, co_author=co_author)
        except git.InvalidGitRepositoryError:
            return "Error: Not a git repository"
        except git.GitCommandError as e:
            return f"Error during auto commit: {e}"


if __name__ == "__main__":
    import asyncio

    from arox import agent_patterns
    from arox.config import TomlConfigParser

    toml_parser = TomlConfigParser()
    agent_patterns.init(toml_parser)

    async def main():
        agent = GitCommitAgent("git_commit_agent", toml_parser)
        result = await agent.auto_commit_changes()
        print(result)

    asyncio.run(main())
