from recommendation_system.modules.locustfile import HttpUser, task, between

class ChatbotUser(HttpUser):
    wait_time = between(1, 3)
    
    @task
    def send_message(self):
        self.client.post("/chat", json={"message": "найди кафе", "user_id": "test_123"})
    
    @task(2)
    def health_check(self):
        self.client.get("/health")