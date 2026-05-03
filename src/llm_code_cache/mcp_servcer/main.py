from mcp.server.fastmcp import FastMCP


mcp = FastMCP("weather")


NWS_API_BASE = "https://api.weather.gov"
USER_AGENT = "weather-app/1.0"

def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
