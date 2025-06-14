import yaml
from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding.key_bindings import KeyBindings


def deep_merge(source, overrides):
    """Deep merge two dictionaries, with overrides taking precedence"""
    for key, value in overrides.items():
        if isinstance(value, dict) and key in source:
            source[key] = deep_merge(source.get(key, {}), value)
        else:
            source[key] = value
    return source


def parse_dict(value: str) -> dict:
    """Parse a string of key=value pairs into a dictionary"""
    if not value.strip():
        return {}
    return dict(yaml.safe_load(value))


def user_input_generator(
    cached_human_responses=[],
    cached_response_index=0,
    force_cached=False,
    completer=None,
):
    """Async generator that yields user input"""

    async def wrapper():
        nonlocal cached_response_index
        history = FileHistory(".llmse6_history")
        kb = KeyBindings()

        @kb.add("enter")
        def _(event):  # Enter to submit
            event.current_buffer.validate_and_handle()

        @kb.add("escape", "enter")  # Alt+Enter newline
        @kb.add("escape", "O", "M")  # Shift+Enter (at least in my konsole)
        def _(event):
            event.current_buffer.insert_text("\n")

        session = PromptSession(
            prompt_continuation="> ",
            multiline=True,
            key_bindings=kb,
            history=history,
            auto_suggest=AutoSuggestFromHistory(),
            mouse_support=False,
            completer=completer,
        )
        while True:
            try:
                if force_cached:
                    user_input = cached_human_responses[cached_response_index]
                    cached_response_index += 1
                    print(f"(cached): {user_input}\n")
                else:
                    user_input = await session.prompt_async("User (q/Q to quit): ")
            except EOFError:
                user_input = cached_human_responses[cached_response_index]
                cached_response_index += 1
                print(f"(cached): {user_input}\n")
            if user_input in {"q", "Q"}:
                print("AI: Byebye")
                break
            yield user_input

    return wrapper()


def xml_wrap(contents: list[tuple[str, str]]) -> str:
    xmled = []
    for tag, content in contents:
        if content is not None:
            xmled.append(f"<{tag}>\n{content}\n</{tag}>\n")
    return "\n".join(xmled)
