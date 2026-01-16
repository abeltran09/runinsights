class BaseIngestor:
    def get_connections(self):
        pass

    def ingest(self, connection):
        pass

    def run(self):
        for conn in self.get_connections():
            self.ingest(conn)