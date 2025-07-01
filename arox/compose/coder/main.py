import argparse
import asyncio
import logging
import sys
from pathlib import Path

from kissllm.tools import LocalToolManager

from arox import agent_patterns, commands, config
from arox.agent_patterns.chat import ChatAgent
from arox.agent_patterns.llm_base import LLMBaseAgent
from arox.commands import CommandCompleter
from arox.compose.coder.state import CoderState
from arox.compose.git_commit import GitCommitAgent
from arox.config import TomlConfigParser
from arox.tools import file_edit, search_reading
from arox.utils import run_command, user_input_generator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CoderComposer:
    def __init__(self):
        parser = argparse.ArgumentParser()

        parser.add_argument(
            "--dump-default-config",
            help="Dump default config to specified file and exit.",
            default="",
        )
        args, unknown_args = parser.parse_known_args()
        cli_configs = config.parse_dot_config(unknown_args)

        default_agent_config = Path(__file__).parent / "config.toml"
        toml_parser = TomlConfigParser(
            config_files=[default_agent_config], override_configs=cli_configs
        )

        self.name = "coder"
        composer_group = toml_parser.add_argument_group(
            name=f"composer.{self.name}", expose_raw=True
        )
        composer_group.add_argument("pre_commit_cmd", default=None)
        self.config = toml_parser.parse_args()
        composer_config = getattr(self.config.composer, self.name)
        self.pre_commit_cmd = composer_config.pre_commit_cmd

        agent_patterns.init(toml_parser)
        local_tool_manager = LocalToolManager()

        diff_agent = LLMBaseAgent("smart-diff", toml_parser)
        file_edit_tool = file_edit.FileEdit(diff_agent)
        file_edit_tool.register_tools(local_tool_manager)
        self.diff_agent = diff_agent

        git_commit_agent = GitCommitAgent("git_commit_agent", toml_parser)
        self.commit_agent = git_commit_agent

        coder_agent = ChatAgent(
            "coder",
            toml_parser,
            local_tool_manager,
            CoderState,
            context={"commit_agent": self.commit_agent},
        )
        sr_tool = search_reading.SearchReading(coder_agent.state)
        sr_tool.register_tools(local_tool_manager)

        coder_commands = [
            commands.FileCommand(coder_agent),
            commands.ModelCommand(coder_agent),
            commands.InvokeToolCommand(coder_agent),
            commands.ListToolCommand(coder_agent),
            commands.ResetCommand(coder_agent),
            commands.InfoCommand(coder_agent),
            commands.CommitCommand(coder_agent),
        ]
        coder_agent.register_commands(coder_commands)

        self.coder_agent = coder_agent

        # Add commit hooks
        async def before_llm_hook(agent, input_content: str):
            logger.info("Running pre-LLM commit hook")
            await self.commit_agent.auto_commit_changes()

        async def after_llm_hook(agent, input_content: str):
            logger.info("Running post-LLM commit hook")
            if self.pre_commit_cmd:
                stdout, stderr, returncode = await run_command(self.pre_commit_cmd)
                if returncode != 0:
                    logger.error(f"Pre-commit command failed: {self.pre_commit_cmd}")
                    logger.error(f"stdout: {stdout}")
                    logger.error(f"stderr: {stderr}")

            co_author = f"arox-coder/{agent.provider_model}"
            await self.commit_agent.auto_commit_changes(co_author=co_author)

        self.coder_agent.add_before_llm_node_hook(before_llm_hook)
        self.coder_agent.add_after_llm_node_hook(after_llm_hook)

        if args.dump_default_config:
            logger.debug(f"Dumping default config to {args.dump_default_config}")
            with open(args.dump_default_config, "w") as f:
                toml_parser.dump_default_config(f)
            sys.exit(0)

    async def run(self):
        logger.debug("Starting coder agent")
        await self.coder_agent.start(
            user_input_generator(
                completer=CommandCompleter(self.coder_agent.command_manager)
            )
        )


def main():
    asyncio.run(CoderComposer().run())


if __name__ == "__main__":
    main
