run:
	@echo "Running Marketeer in Docker\n"
	@docker build -t marketeer .
	@docker run -it --rm marketeer

local:
	@echo "Running Marketeer Locally\n"
	@export ENV=development && python3 main.py
