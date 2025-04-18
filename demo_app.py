import streamlit as st
import asyncio
import os
import plotly.graph_objects as go
from pathlib import Path
from dotenv import load_dotenv

# Ensure we're loading the .env from the core/integrations directory
current_dir = Path(__file__).parent
integrations_dir = current_dir / 'core' / 'integrations'
dotenv_path = integrations_dir / '.env'
load_dotenv(dotenv_path=dotenv_path)

from core.parser.parser import PermissionParser
from core.engine.policy_generator import RegoGenerator
from core.engine.opa_client import OPAClient
from core.integrations import get_integration_mappings, linear_integration
from core.mapper import SimpleSchemaMapper
from core.models import ResourceType, AccessType, AccessRequest, Resource
from core.middleware import PermissionMiddleware
from core.integrations.linear_client import LinearClient


# Set page config
st.set_page_config(
    page_title="Permission Statement Demo",
    page_icon="🔒",
    layout="wide"
)

# App title
st.title("🔒 Permission Statement Interactive Demo")
st.markdown("### Demonstrate how permission statements affect query results")

# Initialize session state for storing statements and test data
if 'statements' not in st.session_state:
    st.session_state.statements = []
if 'test_data' not in st.session_state:
    st.session_state.test_data = []
if 'selected_integration' not in st.session_state:
    st.session_state.selected_integration = "Linear"
if 'opa_policies' not in st.session_state:
    st.session_state.opa_policies = {}
if 'linear_client' not in st.session_state:
    st.session_state.linear_client = None
if 'middleware_config' not in st.session_state:
    # Middleware configuration
    st.session_state.middleware_config = {
        "log_level": "debug",
        "endpoint_configs": {
            "issues.fetch_issues": {
                "type": "collection",
                "item_key": "id",
                "response_format": "tuple"
            },
            "teams.fetch_teams": {
                "type": "collection",
                "item_key": "id"
            }
        }
    }
if 'method_configs' not in st.session_state:
    # Linear method configs
    st.session_state.method_configs = {
        "fetch_issues": {
            "resource_type": ResourceType.ISSUES,
            "action": AccessType.READ,
            "options": {
                "format_hint": "tuple",
                "empty_result": ([], False),
                "debug": True
            }
        },
        "fetch_teams": {
            "resource_type": ResourceType.TEAMS,
            "action": AccessType.READ,
            "options": {
                "format_hint": "tuple",
                "empty_result": ([], False)
            }
        },
        "fetch_projects": {
            "resource_type": ResourceType.PROJECTS,
            "action": AccessType.READ,
            "options": {
                "format_hint": "tuple",
                "empty_result": ([], False)
            }
        }
    }

# Initialize parser and policy generator
parser = PermissionParser(integration_mappings=get_integration_mappings())
generator = RegoGenerator()

# Function to evaluate access for a specific resource against all policies
async def evaluate_access(resource_data, resource_type, action_type="READ"):
    results = []
    
    # Initialize OPA client
    async with OPAClient() as engine:
        # Create access request
        request = AccessRequest(
            action=action_type,
            resource=Resource(
                type=resource_type,
                properties=resource_data
            )
        )
        
        # Check access
        result = await engine.check_access(request)
        results.append({
            "resource": resource_data,
            "allowed": result.allowed,
            "reason": result.reason
        })
        
    return results

# Function to set up Linear client with middleware
async def setup_linear_client():
    try:
        # Get Linear API key from environment
        linear_api_key = os.environ.get("LINEAR_API_KEY")
        if not linear_api_key:
            return None, "LINEAR_API_KEY environment variable is not set"
        
        # Initialize OPA client
        async with OPAClient() as engine:
            # Set up schema mapper and register Linear integration
            mapper = SimpleSchemaMapper()
            await mapper.register_integration(linear_integration)
            
            # Create middleware for Linear integration
            middleware = PermissionMiddleware(
                engine=engine,
                schema_mapper=mapper,
                integration_name="linear",
                config=st.session_state.middleware_config
            )
            
            # Add current permission statements
            for statement_data in st.session_state.statements:
                statement_text = statement_data["text"]
                statement = parser.parse_statement(statement_text)
                policy = await generator.generate_policy(statement)
                policy_id = await engine.add_policy(policy)
                print(f"Added policy for statement: {statement_text}")
            
            # Create middleware-wrapped Linear client
            LinearClientWithPermissions = middleware.apply_to(
                client_class=LinearClient,
                method_configs=st.session_state.method_configs
            )
            
            return LinearClientWithPermissions(api_key=linear_api_key), None
    except Exception as e:
        return None, f"Error setting up Linear client: {str(e)}"

# Utility function to run async functions
def run_async(func):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(func)
    loop.close()
    return result

# Async function to fetch issues from Linear
async def fetch_linear_issues(priority=None, team=None):
    client, error = await setup_linear_client()
    
    if error:
        return None, error
    
    try:
        # Build parameters
        params = {}
        if priority is not None:
            params["priority"] = float(priority)
        if team:
            params["team"] = team
            
        # Use the client directly without an extra context manager
        # since setup_linear_client already created it properly
        issues_tuple = await client.fetch_issues(**params)
        
        # Handle possible None result from middleware
        if issues_tuple is None:
            return [], "All items were filtered due to permissions"
            
        # Safely extract issues from tuple
        if isinstance(issues_tuple, tuple) and len(issues_tuple) > 0:
            issues = issues_tuple[0] if issues_tuple[0] is not None else []
            has_more = issues_tuple[1] if len(issues_tuple) > 1 else False
        else:
            issues = []
            has_more = False
            
        # Important: Close the client properly after use
        await client.close()
            
        return issues, None
    except Exception as e:
        # Make sure to close the client even on error
        try:
            await client.close()
        except:
            pass
        return None, f"Error fetching issues: {str(e)}"

# Sidebar for adding new permission statements
with st.sidebar:
    st.subheader("Create Permission Statements")
    
    # Integration selector (only Linear for now since we're using real data)
    integration = "Linear"
    st.info("Using Linear Integration with real API data")
    
    # API Key status
    linear_api_key = os.environ.get("LINEAR_API_KEY")
    if linear_api_key:
        masked_key = linear_api_key[:4] + "..." + linear_api_key[-4:] if len(linear_api_key) > 8 else "****"
        st.success(f"LINEAR_API_KEY found: {masked_key}")
    else:
        st.error("LINEAR_API_KEY not found in environment variables")
        st.info(f"Looking for .env file at: {dotenv_path}")
    
    # Add tabs for different ways to create statements
    statement_tab1, statement_tab2 = st.tabs(["Builder", "Text Input"])
    
    with statement_tab1:
        st.subheader("Statement Builder")
        # Permission command (GIVE/DENY)
        command = st.selectbox(
            "Command",
            ["GIVE", "DENY"],
            key="builder_command"
        )
        
        # Access type (READ/WRITE/DELETE)
        access_type = st.selectbox(
            "Access Type",
            ["READ", "WRITE", "DELETE"],
            key="builder_access_type"
        )
        
        # Resource type (ISSUES/TEAMS/etc.)
        resource_type = st.selectbox(
            "Resource Type",
            ["ISSUES", "TEAMS", "PROJECTS"],
            key="builder_resource_type"
        )
        
        # Condition builder
        st.subheader("Conditions")
        has_condition = st.checkbox("Add condition", key="builder_has_condition")
        
        if has_condition:
            # Field selector based on resource type
            if resource_type == "ISSUES":
                field_options = ["PRIORITY", "TEAM", "ASSIGNEE", "STATUS"]
            elif resource_type == "TEAMS":
                field_options = ["NAME", "OWNER", "MEMBERS"]
            else:
                field_options = ["NAME", "TEAM"]
                
            condition_field = st.selectbox(
                "Field",
                field_options,
                key="builder_condition_field"
            )
            
            # Operator selector
            operator_options = ["IS", "IS_NOT", "GREATER_THAN", "LESS_THAN", "CONTAINS"]
            condition_operator = st.selectbox(
                "Operator",
                operator_options,
                key="builder_condition_operator"
            )
            
            # Value input (depends on field)
            if condition_field == "PRIORITY":
                condition_value = st.number_input(
                    "Value",
                    min_value=0,
                    max_value=4,
                    step=1,
                    value=1,
                    key="builder_condition_value_num"
                )
            else:
                condition_value = st.text_input(
                    "Value",
                    key="builder_condition_value_text"
                )
            
            # Preview the condition
            if condition_field and condition_operator:
                if condition_operator in ["IS", "IS_NOT"]:
                    condition_preview = f"WITH {condition_field} {condition_operator} {condition_value}"
                else:
                    condition_preview = f"WITH {condition_field} {condition_operator} {condition_value}"
                st.success(f"Condition: {condition_preview}")
            
        # Generate the full statement
        if resource_type:
            if has_condition and condition_field and condition_operator:
                full_statement = f"{command} {access_type} ACCESS TO {resource_type} {condition_preview}"
            else:
                full_statement = f"{command} {access_type} ACCESS TO {resource_type}"
                
            st.markdown("### Generated Statement")
            st.code(full_statement)
            
            if st.button("Add Statement from Builder"):
                try:
                    # Parse statement
                    statement = parser.parse_statement(full_statement)
                    
                    # Generate policy
                    policy = run_async(generator.generate_policy(statement))
                    
                    # Add to session state
                    st.session_state.statements.append({
                        "text": full_statement,
                        "parsed": statement.dict(),
                        "policy": policy.dict()
                    })
                    
                    # Store policy ID to simulate OPA policy management
                    st.session_state.opa_policies[full_statement] = policy.policy_content
                    
                    st.success(f"Statement added: {full_statement}")
                except Exception as e:
                    st.error(f"Error parsing statement: {str(e)}")
    
    # Second tab with text input
    with statement_tab2:
        # Example statements based on integration
        example_statements = {
            "Linear": [
                "GIVE READ ACCESS TO ISSUES WITH PRIORITY = 1",
                "GIVE READ ACCESS TO TEAMS",
                "DENY READ ACCESS TO ISSUES WITH PRIORITY = 3"
            ]
        }
        
        # Dropdown for example statements
        selected_example = st.selectbox(
            "Example Statements",
            example_statements.get(integration, ["No examples available"]),
            index=0
        )
        
        # Text area for statement input
        statement_text = st.text_area(
            "Permission Statement",
            value=selected_example,
            height=100
        )
        
        # Add statement button
        if st.button("Add Statement from Text"):
            try:
                # Parse statement
                statement = parser.parse_statement(statement_text)
                
                # Generate policy
                policy = run_async(generator.generate_policy(statement))
                
                # Add to session state
                st.session_state.statements.append({
                    "text": statement_text,
                    "parsed": statement.dict(),
                    "policy": policy.dict()
                })
                
                # Store policy ID to simulate OPA policy management
                st.session_state.opa_policies[statement_text] = policy.policy_content
                
                st.success(f"Statement added: {statement_text}")
            except Exception as e:
                st.error(f"Error parsing statement: {str(e)}")
    
    # Clear all statements button
    if st.button("Clear All Statements"):
        st.session_state.statements = []
        st.session_state.opa_policies = {}
        st.success("All statements cleared")

# Main content area with tabs
tab1, tab2, tab3 = st.tabs(["Statements & Policies", "Linear Data Visualization", "Middleware Testing"])

# Tab 1: Statements and Policies
with tab1:
    if not st.session_state.statements:
        st.info("Add statements using the sidebar to see them here.")
    else:
        for i, statement_data in enumerate(st.session_state.statements):
            with st.expander(f"Statement {i+1}: {statement_data['text']}", expanded=i==0):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("Parsed Statement")
                    st.json(statement_data["parsed"])
                
                with col2:
                    st.subheader("Generated Rego Policy")
                    st.code(statement_data["policy"]["policy_content"], language="rego")
                
                # Add validation section
                st.subheader("Validate Statement")
                validate_cols = st.columns(2)
                
                with validate_cols[0]:
                    if st.button(f"Test with Sample Data", key=f"test_sample_{i}"):
                        # Create sample data for testing this particular statement
                        sample_data = []
                        
                        # Extract statement info
                        statement_resource = statement_data["parsed"]["resource_type"]
                        has_conditions = len(statement_data["parsed"]["conditions"]) > 0
                        
                        if statement_resource == "ISSUES":
                            # Create sample issues with different priorities
                            for p in range(1, 5):
                                sample_data.append({
                                    "id": f"sample-{p}",
                                    "identifier": f"ISSUE-{p}",
                                    "title": f"Sample Issue {p}",
                                    "priority": float(p),
                                    "team": "Sample Team"
                                })
                        
                        st.session_state.validation_data = {
                            "statement_idx": i,
                            "sample_data": sample_data
                        }
                
                with validate_cols[1]:
                    if st.button(f"Test with Real Data", key=f"test_real_{i}"):
                        with st.spinner("Fetching real data to test statement..."):
                            # Fetch real data for the statement's resource type
                            if statement_data["parsed"]["resource_type"] == "ISSUES":
                                # Fetch issues with minimal filtering
                                test_data, error = run_async(fetch_linear_issues())
                                
                                if error:
                                    st.error(f"Error fetching data: {error}")
                                else:
                                    st.session_state.validation_data = {
                                        "statement_idx": i,
                                        "sample_data": test_data if test_data else []
                                    }
                
                # Show validation results if available
                if 'validation_data' in st.session_state and st.session_state.validation_data["statement_idx"] == i:
                    validation_data = st.session_state.validation_data["sample_data"]
                    st.subheader("Validation Results")
                    
                    # Validate each item against the statement
                    allowed_items = []
                    denied_items = []
                    
                    # Simplified validation logic for demo purposes
                    # In a real system, this would use the actual OPA evaluation
                    for item in validation_data:
                        is_allowed = True
                        
                        # Basic condition checking for demo purposes
                        for condition in statement_data["parsed"]["conditions"]:
                            if condition["field"] == "priority" and condition["operator"] == "IS":
                                if float(item.get("priority", 0)) == float(condition["value"]):
                                    # This matches the condition
                                    if statement_data["parsed"]["command"] == "DENY":
                                        is_allowed = False
                                elif statement_data["parsed"]["command"] == "GIVE":
                                    # Doesn't match the positive condition
                                    is_allowed = False
                        
                        if is_allowed:
                            allowed_items.append(item)
                        else:
                            denied_items.append(item)
                    
                    # Display the results
                    st.markdown(f"**Total items tested:** {len(validation_data)}")
                    st.markdown(f"**Items allowed:** {len(allowed_items)}")
                    st.markdown(f"**Items denied:** {len(denied_items)}")
                    
                    # Show the affected items
                    result_cols = st.columns(2)
                    
                    with result_cols[0]:
                        st.markdown("### ✅ Allowed Items")
                        if allowed_items:
                            for item in allowed_items:
                                item_id = item.get("identifier", item.get("id", "Unknown"))
                                st.success(f"{item_id} - Priority: {item.get('priority', 'N/A')}")
                        else:
                            st.info("No items were allowed by this statement")
                    
                    with result_cols[1]:
                        st.markdown("### ❌ Denied Items")
                        if denied_items:
                            for item in denied_items:
                                item_id = item.get("identifier", item.get("id", "Unknown"))
                                st.error(f"{item_id} - Priority: {item.get('priority', 'N/A')}")
                        else:
                            st.info("No items were denied by this statement")
                            
                # Remove button
                if st.button(f"Remove Statement {i+1}"):
                    del st.session_state.statements[i]
                    st.experimental_rerun()

# Tab 2: Linear Data Visualization
with tab2:
    st.subheader("Test Permission Enforcement with Real Linear Data")
    
    # Check for API key first
    if not os.environ.get("LINEAR_API_KEY"):
        st.error("LINEAR_API_KEY environment variable is not set. Cannot fetch real data.")
    else:
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.markdown("### Query Configuration")
            
            # Configure issue query
            priority_filter = st.number_input("Priority Filter", min_value=0, max_value=4, value=3, key="viz_priority")
            team_filter = st.text_input("Team Filter (optional)", key="viz_team_filter")
            
            # Button to fetch real data
            if st.button("Fetch Linear Issues"):
                with st.spinner("Fetching data from Linear API..."):
                    # Fetch real Linear issues with middleware filtering
                    issues, error = run_async(fetch_linear_issues(priority=priority_filter, team=team_filter))
                    
                    if error:
                        st.error(f"Error: {error}")
                    
                    st.session_state.test_data = issues if issues else []
                    
                    if issues is not None:
                        st.success(f"Fetched {len(issues)} issues after permission filtering")
            
            # Show the current data
            if 'test_data' in st.session_state and st.session_state.test_data:
                st.markdown(f"### Retrieved {len(st.session_state.test_data)} Issues")
                st.json(st.session_state.test_data)
            else:
                st.info("No data fetched yet or all issues were filtered out by permissions")
        
        with col2:
            st.markdown("### Results Visualization")
            
            if 'test_data' in st.session_state and st.session_state.test_data:
                # Create visualization with actual data
                test_data = st.session_state.test_data
                
                # Figure out what attributes are in the data
                all_keys = set()
                for item in test_data:
                    all_keys.update(item.keys())
                
                # Let user select which attribute to visualize
                primary_attribute = st.selectbox(
                    "Attribute to Visualize",
                    sorted(list(all_keys)),
                    index=0 if "priority" in all_keys else 0
                )
                
                # Visualization using Plotly
                fig = go.Figure()
                
                # Add trace for issues by attribute
                values = [item.get(primary_attribute, "N/A") for item in test_data]
                ids = [item.get("identifier", item.get("id", f"Item-{i}")) for i, item in enumerate(test_data)]
                
                if ids:  
                    fig.add_trace(go.Bar(
                        x=ids,
                        y=values if all(isinstance(v, (int, float)) for v in values if v != "N/A") else [1] * len(ids),
                        text=values if not all(isinstance(v, (int, float)) for v in values if v != "N/A") else None,
                        marker_color='blue',
                        name='Issues',
                        hovertemplate='%{x}<br>%{y}<extra></extra>'
                    ))
                    
                    fig.update_layout(
                        title=f"Linear Issues by {primary_attribute}",
                        xaxis_title="Issue Identifier",
                        yaxis_title=primary_attribute,
                        height=400
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Show data distribution table
                    if primary_attribute in test_data[0]:
                        # Create frequency count
                        value_counts = {}
                        for item in test_data:
                            val = item.get(primary_attribute)
                            if val in value_counts:
                                value_counts[val] += 1
                            else:
                                value_counts[val] = 1
                        
                        # Display summary table
                        st.markdown("### Data Distribution")
                        summary_data = {
                            primary_attribute: list(value_counts.keys()),
                            "Count": list(value_counts.values())
                        }
                        st.dataframe(summary_data)
                else:
                    st.warning("No data available for visualization after permission filtering")
            else:
                st.info("Fetch data to see visualization")

# Tab 3: Middleware Testing
with tab3:
    st.subheader("Test Middleware with Different Settings")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.markdown("### Configure Test")
        
        # Select method to test
        test_method = st.selectbox(
            "API Method",
            ["fetch_issues", "fetch_teams", "fetch_projects"],
            index=0
        )
        
        # Parameters for the method
        if test_method == "fetch_issues":
            test_priority = st.number_input("Priority Filter", min_value=0, max_value=4, step=1, value=3, key="test_priority")
            test_team = st.text_input("Team Filter (optional)", key="test_team_filter")
            
            # Build parameters object
            params = {
                "priority": float(test_priority)  # Ensure correct type for Linear's API
            }
            if test_team:
                params["team"] = test_team
                
            st.json(params)
    
    with col2:
        st.markdown("### Middleware Test Results")
        
        if st.button("Execute Test with Real Middleware"):
            with st.spinner("Running test with middleware..."):
                try:
                    # Setup client with actual middleware
                    client_class, setup_error = run_async(setup_linear_client())
                    
                    if setup_error:
                        st.error(f"Setup error: {setup_error}")
                    else:
                        # Build parameters
                        test_params = {}
                        if test_method == "fetch_issues":
                            if test_priority is not None:
                                test_params["priority"] = float(test_priority)
                            if test_team:
                                test_params["team"] = test_team
                        
                        # Format parameters for display
                        params_display = ", ".join([f"{k}={v}" for k, v in test_params.items()])
                        
                        # Show execution plan
                        st.markdown("#### Test Execution Plan")
                        st.code(f"client.{test_method}({params_display})", language="python")
                        
                        # Execute the actual API call through middleware
                        async def execute_test():
                            # Don't use a context manager here, to avoid premature client closure
                            method = getattr(client_class, test_method)
                            result = await method(**test_params)
                            
                            # Important: Close the client properly after all operations
                            try:
                                await client_class.close()
                            except:
                                pass
                                
                            return result
                        
                        # Run the test
                        result = run_async(execute_test())
                        
                        # Display results
                        st.markdown("#### Results")
                        
                        if result is None:
                            st.warning("All results filtered out by permission middleware")
                            st.code("([], False)  # Empty result with has_more=False", language="python")
                        elif isinstance(result, tuple) and len(result) > 0:
                            items = result[0] if result[0] is not None else []
                            has_more = result[1] if len(result) > 1 else False
                            
                            st.success(f"Retrieved {len(items)} items after permission filtering")
                            st.json(items)
                            st.info(f"has_more: {has_more}")
                        else:
                            st.info(f"Result: {result}")
                        
                except Exception as e:
                    st.error(f"Error executing test: {str(e)}")
                    st.exception(e)

# Footer
st.markdown("---")
st.markdown("🔐 **Permission Statement Demo with Real Linear API** | Built with Streamlit | Uses actual permission middleware") 