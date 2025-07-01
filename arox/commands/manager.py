import asyncio

from . import Command, CommandCompleter, parse_cmdline


class CommandManager:
    def __init__(self, agent):
        self.command_map = {}
        self.agent = agent
        self.completer = CommandCompleter(self.agent)

    def register_commands(self, commands: list[Command]):
        for command in commands:
            for s in command.slashes():
                self.command_map[s] = command

    async def try_execute_command(self, user_input: str) -> bool:
        c_name, c_arg = parse_cmdline(user_input)
        if not c_name:
            return False

        command = self.command_map.get(c_name)
        if command:
            if asyncio.iscoroutinefunction(command.execute):
                await command.execute(c_name, c_arg)
            else:
                command.execute(c_name, c_arg)
        else:
            print(f"Command not found: {user_input}")
        return True

    def get_completions(self, name: str, args: str, document):
        command = self.command_map.get(name)
        if not command:
            return
        yield from command.get_completions(name, args, document)

    def command_names(self):
        return self.command_map.keys()
