import gurobipy as gp
from gurobipy import GRB
import numpy as np

# === STEP 1: Set WLS license credentials ===
# Replace with your actual license details
WLS_ACCESS_ID = "5d7a35f3-7b2e-477d-902c-1e16aae432ba"
WLS_SECRET = "067968bb-f8df-4faa-8fcb-6b5813574d90"
LICENSE_ID = 2790310  # Replace with your numeric license ID

try:
    # === STEP 2: Create and start environment with WLS license ===
    env = gp.Env(empty=True)
    env.setParam("WLSAccessID", WLS_ACCESS_ID)
    env.setParam("WLSSecret", WLS_SECRET)
    env.setParam("LicenseID", LICENSE_ID)
    env.start()

    ##################################################
    num_factories = 100
    num_products = 20
    num_zones = 200

    np.random.seed(42)

    # Capacity per factory
    capacity = np.random.randint(500, 1500, size=num_factories)

    # Demand per product per zone
    demand = np.random.randint(10, 100, size=(num_products, num_zones))

    # Production cost per unit (factory × product)
    prod_cost = np.random.uniform(1, 10, size=(num_factories, num_products))

    # Shipping cost per unit (factory × zone)
    ship_cost = np.random.uniform(0.5, 5.0, size=(num_factories, num_zones))

    # Create model
    model = gp.Model("large_scale_production")

    # Decision vars: x[f,p,z] = units of product p produced at factory f and shipped to zone z
    x = model.addVars(
        num_factories, num_products, num_zones,
        lb=0, vtype=GRB.CONTINUOUS, name="x"
    )

    # Objective: Minimize total cost = production + shipping
    model.setObjective(
        gp.quicksum(x[f, p, z] * (prod_cost[f, p] + ship_cost[f, z])
                    for f in range(num_factories)
                    for p in range(num_products)
                    for z in range(num_zones)),
        GRB.MINIMIZE
    )

    # Demand constraints: each zone must receive required demand for each product
    for p in range(num_products):
        for z in range(num_zones):
            model.addConstr(
                gp.quicksum(x[f, p, z] for f in range(num_factories)) >= demand[p, z],
                name=f"demand_p{p}_z{z}"
            )

    # Factory capacity constraints: total units produced at a factory must not exceed capacity
    for f in range(num_factories):
        model.addConstr(gp.quicksum(x[f, p, z] for p in range(num_products) for z in range(num_zones)) <= capacity[f],
                        name=f"capacity_f{f}")

    # Optional: Disable certain product-factory combinations (e.g., factory f can’t produce product p)
    # For extra realism: randomly disable ~10% of combinations
    for f in range(num_factories):
        for p in range(num_products):
            if np.random.rand() < 0.1:
                for z in range(num_zones):
                    x[f, p, z].ub = 0  # Force those variables to 0

    # Optimize
    model.optimize()

    # Print result
    if model.status == gp.GRB.OPTIMAL:
        print(f"✅ Gurobi WLS license is working")
    else:
        print("❌ Model did not solve. Check license or model definition.")

    # === STEP 3: Define a large LP model ===
    print("Building large model...")
    model = gp.Model("LargeLP", env=env)

    num_vars = 15000
    num_constraints = 1500

    # Create decision variables: x_0, x_1, ..., x_2999
    x = model.addVars(num_vars, lb=0, name="x")

    # Objective: Minimize the sum of all x variables
    model.setObjective(gp.quicksum(x[i] for i in range(num_vars)), GRB.MINIMIZE)

    # Constraints: each constraint sums 100 variables and must be ≥ 50
    for i in range(num_constraints):
        start = i
        end = min(i + 100, num_vars)
        model.addConstr(gp.quicksum(x[j] for j in range(start, end)) >= 50, name=f"c{i}")

    # === STEP 4: Solve the model ===
    print("Optimizing...")
    model.optimize()

    # === STEP 5: Print summary ===
    if model.status == GRB.OPTIMAL:
        print(f"\n✅ Model solved optimally.")
        print(f"Objective value: {model.ObjVal:.4f}")
    else:
        print(f"\n❌ Model did not solve successfully. Status code: {model.status}")

except gp.GurobiError as e:
    print(f"\n❌ GurobiError: {e}")
except Exception as e:
    print(f"\n❌ Other error: {e}")

# Create a new Gurobi environment
env = gp.Env(empty=True)

# Set WLS license parameters
env.setParam("WLSAccessID", "96daee41-16c8-4add-a427-2028f293967a")
env.setParam("WLSSecret", "23a86426-6aa9-4181-9ebd-774a96e2ffc7")
env.setParam("LicenseID", 2790310)  # Replace with your numeric license ID

# Start the environment (connects to Gurobi WLS server)
env.start()

# Create and solve a small test model using this environment
model = gp.Model("test_model", env=env)
x = model.addVar(lb=0, name="x")
model.setObjective(x, gp.GRB.MAXIMIZE)
model.addConstr(x <= 5, name="c1")
model.optimize()

# Print result
if model.status == gp.GRB.OPTIMAL:
    print(f"✅ Gurobi WLS license is working. Solution: x = {x.X}")
else:
    print("❌ Model did not solve. Check license or model definition.")

# Parameters
num_factories = 100
num_products = 20
num_zones = 200

np.random.seed(42)

# Capacity per factory
capacity = np.random.randint(500, 1500, size=num_factories)

# Demand per product per zone
demand = np.random.randint(10, 100, size=(num_products, num_zones))

# Production cost per unit (factory × product)
prod_cost = np.random.uniform(1, 10, size=(num_factories, num_products))

# Shipping cost per unit (factory × zone)
ship_cost = np.random.uniform(0.5, 5.0, size=(num_factories, num_zones))

# Create model
model = gp.Model("large_scale_production")

# Decision vars: x[f,p,z] = units of product p produced at factory f and shipped to zone z
x = model.addVars(
    num_factories, num_products, num_zones,
    lb=0, vtype=GRB.CONTINUOUS, name="x"
)

# Objective: Minimize total cost = production + shipping
model.setObjective(
    gp.quicksum(x[f, p, z] * (prod_cost[f, p] + ship_cost[f, z])
                for f in range(num_factories)
                for p in range(num_products)
                for z in range(num_zones)),
    GRB.MINIMIZE
)

# Demand constraints: each zone must receive required demand for each product
for p in range(num_products):
    for z in range(num_zones):
        model.addConstr(
            gp.quicksum(x[f, p, z] for f in range(num_factories)) >= demand[p, z],
            name=f"demand_p{p}_z{z}"
        )

# Factory capacity constraints: total units produced at a factory must not exceed capacity
for f in range(num_factories):
    model.addConstr(gp.quicksum(x[f, p, z] for p in range(num_products) for z in range(num_zones)) <= capacity[f],
                    name=f"capacity_f{f}")

# Optional: Disable certain product-factory combinations (e.g., factory f can’t produce product p)
# For extra realism: randomly disable ~10% of combinations
for f in range(num_factories):
    for p in range(num_products):
        if np.random.rand() < 0.1:
            for z in range(num_zones):
                x[f, p, z].ub = 0  # Force those variables to 0

# Optimize
model.optimize()

# Print result
if model.status == gp.GRB.OPTIMAL:
    print(f"✅ Gurobi WLS license is working")
else:
    print("❌ Model did not solve. Check license or model definition.")