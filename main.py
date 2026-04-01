"""Minimal example: run the agent from the command line."""

from langchain_openai import ChatOpenAI

from llm_agent import LLMAgent


def main() -> None:
    llm = ChatOpenAI(model="gpt-4o")
    agent = LLMAgent(llm).setup()

    while True:
        try:
            user_input = input("\nYou: ")
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not user_input.strip():
            continue

        response = agent.invoke(user_input)
        print(f"Agent: {response}")


if __name__ == "__main__":
    main()
