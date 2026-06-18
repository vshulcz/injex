from abc import ABC, abstractmethod

from injex import Container, LifeStyle, inject


class IDatabaseConnection(ABC):
    @abstractmethod
    def execute_query(self, query: str): ...


class MySQLConnection(IDatabaseConnection):
    def execute_query(self, query: str):
        print(f"MySQL executing query: {query}")


class PostgreSQLConnection(IDatabaseConnection):
    def execute_query(self, query: str):
        print(f"PostgreSQL executing query: {query}")


class ICache(ABC):
    @abstractmethod
    def get(self, key: str): ...


class RedisCache(ICache):
    def get(self, key: str):
        print(f"RedisCache getting key: {key}")


class DataService:
    def __init__(self, db_connection: IDatabaseConnection, cache: ICache | None = None):
        self.db_connection = db_connection
        self.cache = cache

    @inject
    def logger(self) -> "ILogger": ...

    def get_data(self, key: str):
        if self.cache:
            self.cache.get(key)
        self.db_connection.execute_query(f"SELECT * FROM data WHERE key = '{key}'")
        self.logger.log(f"Data retrieved for key: {key}")


class ILogger(ABC):
    @abstractmethod
    def log(self, message: str): ...


class FileLogger(ILogger):
    def log(self, message: str):
        with open("data_service.log", "a") as f:
            f.write(f"{message}\n")


def db_connection_factory() -> IDatabaseConnection:
    # Choose the implementation from config, env, etc.
    return MySQLConnection()


container = Container()

container.register_factory(
    IDatabaseConnection, db_connection_factory, lifestyle=LifeStyle.SCOPED
)
container.register(ICache, RedisCache, lifestyle=LifeStyle.SINGLETON)
container.register(ILogger, FileLogger, lifestyle=LifeStyle.SINGLETON)
container.register(DataService)

scope = container.create_scope()

data_service = scope.resolve(DataService)
data_service.get_data("Test")
