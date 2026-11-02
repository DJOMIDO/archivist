from dotenv import load_dotenv
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tracers.langchain import wait_for_all_tracers

load_dotenv(dotenv_path=".env")

prompt = ChatPromptTemplate.from_messages([("human", "What is {topic}?")])
model = FakeListChatModel(
    responses=["RAG answers questions using retrieved documents."]
)
chain = prompt | model | StrOutputParser()

print(chain.invoke({"topic": "embeddings"}, config={"run_name": "tracing-smoke-test"}))
wait_for_all_tracers()
