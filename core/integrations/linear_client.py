"""Linear API client for interacting with Linear's GraphQL API."""

import logging
from typing import Dict, List, Optional, Any, Tuple

import httpx

# Set up logging
logger = logging.getLogger(__name__)

class LinearClient:
    """Client for interacting with Linear's GraphQL API."""
    
    def __init__(self, api_key: str):
        """
        Initialize the Linear client.
        
        Args:
            api_key: The Linear API key
        """
        self.api_url = "https://api.linear.app/graphql"
        self.api_key = api_key.strip().replace('"', '')  # Remove quotes if present
        
        # Some API clients require different header formats, so we'll try the standard way
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": self.api_key  # Pass the API key directly as per Linear docs
        }
        self.http_client = httpx.AsyncClient(timeout=10.0)
    
    async def __aenter__(self) -> "LinearClient":
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()
    
    async def close(self) -> None:
        """Close the HTTP client and release resources."""
        await self.http_client.aclose()
    
    async def execute_query(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute a GraphQL query against the Linear API.
        
        Args:
            query: The GraphQL query to execute
            variables: Variables for the query
            
        Returns:
            Dict[str, Any]: The query result
        """
        try:
            print(f"Executing GraphQL query with variables: {variables}")
            
            response = await self.http_client.post(
                self.api_url,
                headers=self.headers,
                json={"query": query, "variables": variables or {}}
            )
            
            # Print full response status and body for debugging
            print(f"Response status: {response.status_code}")
            try:
                response_json = response.json()
                print(f"Response body: {response_json}")
                
                if "errors" in response_json:
                    error_details = response_json["errors"]
                    print(f"GraphQL errors: {error_details}")
            except Exception as e:
                print(f"Could not parse response as JSON: {str(e)}")
                print(f"Response text: {response.text}")
            
            response.raise_for_status()
            
            result = response.json()
            
            if "errors" in result:
                error_msg = result["errors"][0].get("message", "Unknown GraphQL error")
                logger.error(f"GraphQL error: {error_msg}")
                raise ValueError(f"GraphQL error: {error_msg}")
            
            return result.get("data", {})
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP error {e.response.status_code} querying Linear API: {str(e)}"
            
            # Try to extract more details from the error response
            try:
                error_response = e.response.json()
                error_msg += f"\nError details: {error_response}"
            except Exception:
                error_msg += f"\nRaw response: {e.response.text}"
                
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        except httpx.RequestError as e:
            error_msg = f"Request error querying Linear API: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
    
    async def fetch_issues(self, 
                          assignee: Optional[str] = None, 
                          labels: Optional[List[str]] = None, 
                          status: Optional[str] = None,
                          priority: Optional[float] = None,
                          first: int = 100) -> Tuple[List[Dict[str, Any]], bool]:
        """
        Fetch issues from Linear based on criteria.
        
        Args:
            assignee: Filter by assignee name
            labels: Filter by issue labels
            status: Filter by issue state name
            priority: Filter by issue priority (1-4)
            first: Maximum number of issues to fetch
            
        Returns:
            Tuple[List[Dict[str, Any]], bool]: Tuple of (issues list, has_next_page)
        """
        # Build filter variables
        variables = {
            "first": first
        }
        
        # Build filter object directly
        filter_obj = {}
        
        if assignee:
            filter_obj["assignee"] = {"name": {"eq": assignee}}
            
        if labels and len(labels) > 0:
            filter_obj["labels"] = {"name": {"in": labels}}
            
        if status:
            filter_obj["state"] = {"name": {"eq": status}}
            
        if priority is not None:
            # Make sure priority is a float for Linear's API schema
            float_priority = float(priority)
            print(f"[DEBUG] Converting priority {priority} ({type(priority)}) to {float_priority} ({type(float_priority)})")
            filter_obj["priority"] = {"eq": float_priority}
        
        # Add filter to variables if there are any conditions
        if filter_obj:
            variables["filter"] = filter_obj

        # GraphQL query with variables properly used
        query = """
        query IssueSearch($first: Int!, $filter: IssueFilter) {
            issues(first: $first, filter: $filter) {
                nodes {
                    id
                    identifier
                    title
                    description
                    priority
                    estimate
                    dueDate
                    createdAt
                    updatedAt
                    assignee {
                        id
                        name
                        email
                    }
                    state {
                        id
                        name
                        color
                        type
                    }
                    labels {
                        nodes {
                            id
                            name
                            color
                        }
                    }
                    team {
                        id
                        name
                        key
                    }
                    project {
                        id
                        name
                    }
                }
                pageInfo {
                    hasNextPage
                    endCursor
                }
            }
        }
        """
        
        # Execute the query
        result = await self.execute_query(query, variables)
        
        # Process and return the issues
        issues_data = []
        has_next_page = False
        
        if "issues" in result:
            if "nodes" in result["issues"]:
                issues = result["issues"]["nodes"]
                
                # Transform issues to match our internal format
                for issue in issues:
                    # Skip None issues
                    if issue is None:
                        print("Warning: Received None issue in API response, skipping")
                        continue
                        
                    # Extract labels
                    label_list = []
                    if issue.get("labels") and "nodes" in issue["labels"]:
                        label_list = [label["name"] for label in issue["labels"]["nodes"]]
                    
                    # Extract assignee
                    assignee_name = None
                    if issue.get("assignee"):
                        assignee_name = issue["assignee"].get("name")
                    
                    # Extract state/status
                    state_name = None
                    if issue.get("state"):
                        state_name = issue["state"].get("name")
                    
                    # Extract team
                    team_name = None
                    if issue.get("team"):
                        team_name = issue["team"].get("name")
                    
                    # Format dates 
                    created_date = issue.get("createdAt")
                    updated_date = issue.get("updatedAt")
                    due_date = issue.get("dueDate")
                    
                    # Safely get project name
                    project_name = None
                    if issue.get("project"):
                        project_name = issue["project"].get("name")
                    
                    issues_data.append({
                        "id": issue.get("id"),
                        "identifier": issue.get("identifier"),
                        "title": issue.get("title"),
                        "description": issue.get("description"),
                        "priority": issue.get("priority"),
                        "estimate": issue.get("estimate"),
                        "assignee": assignee_name,
                        "labels": label_list,
                        "status": state_name,
                        "team": team_name,
                        "project": project_name,
                        "created_date": created_date,
                        "updated_date": updated_date,
                        "due_date": due_date
                    })
            
            # Check for pagination info
            if "pageInfo" in result["issues"]:
                has_next_page = result["issues"]["pageInfo"].get("hasNextPage", False)
        
        return issues_data, has_next_page
    
    async def fetch_teams(self, 
                         owner: Optional[str] = None,
                         first: int = 50) -> Tuple[List[Dict[str, Any]], bool]:
        """
        Fetch teams from Linear.
        
        Args:
            owner: Filter by team owner name
            first: Maximum number of teams to fetch
            
        Returns:
            Tuple[List[Dict[str, Any]], bool]: Tuple of (teams list, has_next_page)
        """
        # Build filter variables
        variables = {
            "first": first
        }
        
        # Build filter object directly
        filter_obj = {}
        
        if owner:
            filter_obj["members"] = {"name": {"eq": owner}, "admin": True}
        
        # Add filter to variables if there are any conditions
        if filter_obj:
            variables["filter"] = filter_obj
        
        # GraphQL query with variables properly used
        query = """
        query TeamSearch($first: Int!, $filter: TeamFilter) {
            teams(first: $first, filter: $filter) {
                nodes {
                    id
                    name
                    key
                    description
                    color
                    states {
                        nodes {
                            id
                            name
                            color
                            type
                        }
                    }
                    members {
                        nodes {
                            id
                            name
                            email
                            admin
                        }
                    }
                    createdAt
                    updatedAt
                }
                pageInfo {
                    hasNextPage
                    endCursor
                }
            }
        }
        """
        
        # Execute the query
        result = await self.execute_query(query, variables)
        
        # Process and return the teams
        teams_data = []
        has_next_page = False
        
        if "teams" in result:
            if "nodes" in result["teams"]:
                teams = result["teams"]["nodes"]
                
                for team in teams:
                    # Extract members and identify owner/admin
                    members = []
                    owner_name = None
                    
                    if team.get("members") and "nodes" in team["members"]:
                        for member in team["members"]["nodes"]:
                            members.append(member.get("name"))
                            
                            # Admin member is considered an owner
                            if member.get("admin"):
                                if not owner_name:  # First admin found becomes owner
                                    owner_name = member.get("name")
                    
                    # Extract states
                    states = []
                    if team.get("states") and "nodes" in team["states"]:
                        states = [state["name"] for state in team["states"]["nodes"]]
                    
                    teams_data.append({
                        "id": team.get("id"),
                        "name": team.get("name"),
                        "key": team.get("key"),
                        "description": team.get("description"),
                        "color": team.get("color"),
                        "owner": owner_name,
                        "members": members,
                        "states": states,
                        "created_date": team.get("createdAt"),
                        "updated_date": team.get("updatedAt")
                    })
            
            # Check for pagination info
            if "pageInfo" in result["teams"]:
                has_next_page = result["teams"]["pageInfo"].get("hasNextPage", False)
        
        return teams_data, has_next_page
        
    async def fetch_projects(self, 
                           team_id: Optional[str] = None,
                           first: int = 50) -> Tuple[List[Dict[str, Any]], bool]:
        """
        Fetch projects from Linear.
        
        Args:
            team_id: Filter by team ID
            first: Maximum number of projects to fetch
            
        Returns:
            Tuple[List[Dict[str, Any]], bool]: Tuple of (projects list, has_next_page)
        """
        # Build filter variables
        variables = {
            "first": first
        }
        
        # Build filter object directly
        filter_obj = {}
        
        if team_id:
            filter_obj["team"] = {"id": {"eq": team_id}}
        
        # Add filter to variables if there are any conditions
        if filter_obj:
            variables["filter"] = filter_obj
        
        # GraphQL query with variables properly used
        query = """
        query ProjectSearch($first: Int!, $filter: ProjectFilter) {
            projects(first: $first, filter: $filter) {
                nodes {
                    id
                    name
                    description
                    state
                    progress
                    startDate
                    targetDate
                    team {
                        id
                        name
                        key
                    }
                    members {
                        nodes {
                            user {
                                id
                                name
                            }
                        }
                    }
                    leadId
                    createdAt
                    updatedAt
                }
                pageInfo {
                    hasNextPage
                    endCursor
                }
            }
        }
        """
        
        # Execute the query
        result = await self.execute_query(query, variables)
        
        # Process and return the projects
        projects_data = []
        has_next_page = False
        
        if "projects" in result:
            if "nodes" in result["projects"]:
                projects = result["projects"]["nodes"]
                
                for project in projects:
                    # Extract members
                    members = []
                    if project.get("members") and "nodes" in project["members"]:
                        for member in project["members"]["nodes"]:
                            if member.get("user") and member["user"].get("name"):
                                members.append(member["user"]["name"])
                    
                    # Extract team info
                    team_name = None
                    team_key = None
                    if project.get("team"):
                        team_name = project["team"].get("name")
                        team_key = project["team"].get("key")
                    
                    projects_data.append({
                        "id": project.get("id"),
                        "name": project.get("name"),
                        "description": project.get("description"),
                        "state": project.get("state"),
                        "progress": project.get("progress"),
                        "start_date": project.get("startDate"),
                        "target_date": project.get("targetDate"),
                        "team_name": team_name,
                        "team_key": team_key,
                        "members": members,
                        "lead_id": project.get("leadId"),
                        "created_date": project.get("createdAt"),
                        "updated_date": project.get("updatedAt")
                    })
            
            # Check for pagination info
            if "pageInfo" in result["projects"]:
                has_next_page = result["projects"]["pageInfo"].get("hasNextPage", False)
        
        return projects_data, has_next_page 