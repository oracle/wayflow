# How to Perform Data Synthesis in WayFlow![python-icon](_static/icons/python-icon.svg) Download Python Script

Python script/notebook for this guide.

[Data Synthesis how-to script](../end_to_end_code_examples/howto_data_synthesis.py)

This guide provides practical and adaptable methods for generating synthetic datasets tailored to a range of real-world use cases. Use it when you need to create evaluation datasets for model testing, sample data for demonstrations, or address data privacy requirements. You will find reproducible workflows and techniques that you can flexibly adapt to your own data schema and constraints.

Each synthesis approach is presented in relation to specific feature requirements. Most examples start from a seed dataset to capture authentic data characteristics. However, you can also apply these methods without real data by specifying a target schema and using tools such as *Faker*. With this guide, you can generate synthetic data that balances statistical realism with project flexibility.

## Prerequisites and setup
- **Desired output schema:** Define the fields and features your synthetic dataset should contain. Specify each field’s type and any necessary constraints.
- **Seed dataset (optional, recommended):**
  - Use a seed dataset if you want to preserve real-world distributional properties, such as means, variances, or category frequencies.
  - A seed dataset is also essential if you need to interpolate or generate synthetic values conditioned on, or resembling, existing feature values (for example, generating synthetic ages based on a real distribution).
- **No seed dataset?**

  If you do not have real data to start with, you can use the *Faker* package ([Faker](https://faker.readthedocs.io/)). *Faker* provides many generators for structured data such as names, addresses, dates, countries, and phone numbers. Use this to quickly create dummy datasets with any schema, though the values will not reflect empirical sources.

#### NOTE
Choosing whether to use a seed dataset or a synthetic generator depends on your use case.

- For data realism and statistical fidelity, start from a seed dataset.
- For flexible or arbitrary data structures without statistical constraints, use *Faker* or similar tools.

## Target schema and feature properties

The following table summarizes the type, synthesis method, and key properties or constraints for each feature:

- **Interp./Extrap.:** Indicates if the feature is synthesized from existing (seed) values (interpolation) or from new, plausible values (extrapolation).
- **Method or constraint:** Specifies any specialized synthesis function or logic, including use of *Faker*.

#### Load and inspect the seed data

Begin by loading your seed dataset. This data provides distributions, feature values, and coherency patterns for synthetic data generation. For demonstration, the following example defines a small seed dataset matching the target schema above, but you can use your own data.

```python
import pandas as pd

seed_data = [
    {
        "customer_type": "organization",
        "customer_name": "Atlas Engineering Ltd.",
        "region": "EMEA",
        "country": "Germany",
        "customer_net_worth": 75200000,
        "loan_value": 12500000,
        "loan_proposed_interest": 4.9,
        "loan_reason": "Business expansion",
        "justification": "Atlas Engineering Ltd. seeks a $12,500,000 loan at a proposed 4.9% interest to expand its operations across the German automotive sector. With a robust net worth of $75,200,000 and a history of successful project delivery, the company is poised for growth. The expansion will create new jobs and increase market share, while our solid financials and collateral provide strong assurance. This aligns with our strategic business roadmap and justifies a favorable interest rate approval.",
    },
    {
        "customer_type": "individual",
        "customer_name": "Samantha Rivera",
        "region": "NA",
        "country": "United States",
        "customer_net_worth": 1580000,
        "loan_value": 80000,
        "loan_proposed_interest": 3.5,
        "loan_reason": "Home renovation",
        "justification": "Samantha Rivera requests a $80,000 loan at 3.5% interest to renovate her primary residence. With a net worth of $1,580,000 and stable income, Samantha’s credit profile is strong. The renovation will enhance her property value, reducing default risk. Given her responsible financial management and the secured nature of the loan, she is a low-risk borrower deserving of these favorable terms.",
    },
    {
        "customer_type": "organization",
        "customer_name": "MedicoPharma Solutions",
        "region": "JAPAC",
        "country": "Singapore",
        "customer_net_worth": 18500000,
        "loan_value": 4500000,
        "loan_proposed_interest": 5.7,
        "loan_reason": "Investment capital",
        "justification": "MedicoPharma Solutions applies for a $4,500,000 loan at a 5.7% rate to fund critical biotech investments. With a net worth of $18,500,000 and consistent year-over-year growth, the company demonstrates fiscal responsibility. The requested capital is earmarked for new laboratory equipment and R&D, supporting innovation and future revenue. The loan structure and interest rate are well-justified by the company's planned implementations and financial record.",
    },
    {
        "customer_type": "individual",
        "customer_name": "Rajeev Malhotra",
        "region": "JAPAC",
        "country": "India",
        "customer_net_worth": 280000,
        "loan_value": 42000,
        "loan_proposed_interest": 4.2,
        "loan_reason": "Education costs",
        "justification": "Rajeev Malhotra is seeking a $42,000 loan at 4.2% interest to pursue a postgraduate program in Bangalore. With a net worth of $280,000 and a stable employment history, Rajeev is committed to investing in his education for career advancement. The loan will cover tuition and related expenses, and his repayment plan is backed by projected post-graduation earnings, warranting an approval at this rate.",
    },
    {
        "customer_type": "organization",
        "customer_name": "Green Horizons Ltd.",
        "region": "LAD",
        "country": "Brazil",
        "customer_net_worth": 6270000,
        "loan_value": 1300000,
        "loan_proposed_interest": 5.2,
        "loan_reason": "Major appliance",
        "justification": "Green Horizons Ltd. is requesting a $1,300,000 loan with a 5.2% proposed interest rate to acquire industrial-scale solar panel systems for its new facility. With a net worth of $6,270,000, the organization’s history in sustainable development makes this investment logical. The equipment will reduce operational costs and support environmental commitments, providing a compelling rationale for loan approval.",
    },
    {
        "customer_type": "individual",
        "customer_name": "Lucia González",
        "region": "LAD",
        "country": "Argentina",
        "customer_net_worth": 98000,
        "loan_value": 19000,
        "loan_proposed_interest": 6.0,
        "loan_reason": "Debt consolidation",
        "justification": "Lucia González seeks a $19,000 loan at 6.0% interest to consolidate existing debts into a single manageable payment. With a net worth of $98,000 and steady monthly income, Lucia will benefit from simplified repayment terms and reduced overall interest expenses. Her disciplined repayment record supports the requested terms and merits consideration.",
    },
    {
        "customer_type": "organization",
        "customer_name": "BlueStar Trading GmbH",
        "region": "EMEA",
        "country": "Switzerland",
        "customer_net_worth": 26000000,
        "loan_value": 6200000,
        "loan_proposed_interest": 3.3,
        "loan_reason": "Vehicle purchase",
        "justification": "BlueStar Trading GmbH is applying for a $6,200,000 loan at 3.3% interest to upgrade its commercial vehicle fleet in Switzerland. Backed by a $26,000,000 net worth and healthy balance sheet, the acquisition will improve logistics and lower operational costs. Their creditworthiness and the use of vehicles as collateral minimize risk, justifying loan approval at this competitive rate.",
    },
    {
        "customer_type": "individual",
        "customer_name": "Fatima Al-Hassan",
        "region": "EMEA",
        "country": "United Arab Emirates",
        "customer_net_worth": 1200000,
        "loan_value": 38000,
        "loan_proposed_interest": 3.9,
        "loan_reason": "Vacation funding",
        "justification": "Fatima Al-Hassan requests a $38,000 loan at a 3.9% interest rate to cover a family vacation abroad. With a net worth of $1,200,000 and a solid credit score, she is well-positioned to repay the loan comfortably. Her responsible financial history further supports approval at the proposed rate for this short-term, purpose-specific loan.",
    },
    {
        "customer_type": "organization",
        "customer_name": "Aussie Urban Properties",
        "region": "JAPAC",
        "country": "Australia",
        "customer_net_worth": 51200000,
        "loan_value": 9700000,
        "loan_proposed_interest": 4.5,
        "loan_reason": "Business expansion",
        "justification": "Aussie Urban Properties seeks $9,700,000 in funding at a 4.5% interest rate to finance new residential developments in Sydney. With a net worth of $51,200,000 and proven experience in property management, the loan will be efficiently applied. The company’s past successes and robust financial health point to a strong ability to utilize and repay the loan as proposed.",
    },
    {
        "customer_type": "individual",
        "customer_name": "Jacob Peterson",
        "region": "NA",
        "country": "Canada",
        "customer_net_worth": 405000,
        "loan_value": 31000,
        "loan_proposed_interest": 2.7,
        "loan_reason": "Medical expenses",
        "justification": "Jacob Peterson is requesting a $31,000 loan at 2.7% interest to cover medical expenses resulting from an unexpected surgery. With a net worth of $405,000 and reliable employment, Jacob demonstrates strong repayment capacity. His consistent repayment track record and insurance partial coverage will mitigate lender risk, supporting approval at this attractive rate.",
    },
]

df_seed = pd.DataFrame(seed_data)
print(df_seed)
```

## Data synthesis

### Synthesis functions

Define Python functions to generate feature values according to empirical distributions and project-specific constraints.

1. `fake_categorical`: Sample a categorical column by seed frequency
   It uses NumPy to reproduce marginal distributions.

```python
import numpy as np


def fake_categorical(
    rng: np.random.Generator,
    pd_column: pd.Series,
    dropna: bool = False,
    **choice_kwargs: Any,
) -> Any:
    value_counts_dict = pd_column.value_counts(normalize=True, dropna=dropna).to_dict()
    categories = np.array(list(value_counts_dict.keys()))
    probabilities = np.array(list(value_counts_dict.values()))
    return rng.choice(categories, p=probabilities, **choice_kwargs)


```

1. `fake_joint_numerical`: Sample a numerical feature by joint distribution
   It samples values for a numerical feature conditional on one or more categorical features (for example, `customer_net_worth` conditioned on region).

```python
def fake_joint_numerical(
    rng: np.random.Generator,
    df: pd.DataFrame,
    value_col: str,
    cat_cols: str | list[str],
    synthesized_rows: pd.DataFrame,
) -> list[Any]:
    result = []
    cat_array = (
        synthesized_rows[cat_cols].values
        if isinstance(cat_cols, list)
        else synthesized_rows[[cat_cols]].values
    )
    for cats in cat_array:
        mask = np.ones(len(df), dtype=bool)
        if isinstance(cat_cols, list):
            for col, val in zip(cat_cols, cats):
                mask &= df[col].values == val
        else:
            mask &= df[cat_cols].values == cats[0]
        matching_vals = df.loc[mask, value_col]
        if not matching_vals.empty:
            result.append(rng.choice(matching_vals))
        else:
            # Fallback: overall empirical
            result.append(rng.choice(df[value_col]))
    return result


```

## Structured data generation

Each section below demonstrates how to synthesize features while upholding a specific property. After each example, synthesize all other features by specification.

### Reproducibility

Set seeds for all relevant random number generators to make synthesis repeatable.

```python
from faker import Faker

SEED = 0
rng = np.random.default_rng(SEED)
random.seed(SEED)
fake = Faker()
Faker.seed(SEED)
```

### Generation configuration

Configure the synthetic data generation process.

```python
n_synthesized = 20  # adjust as needed
```

### Univariate distribution preservation example (region)

Sample the `region` column according to the frequency distribution in the seed dataset.

```python
synth_region = fake_categorical(rng, df_seed["region"], size=n_synthesized)
print(pd.Series(synth_region).value_counts())
# EMEA     7
# LAD      6
# NA       4
# JAPAC    3
# Name: count, dtype: int64
```

### Coherency constraint example (region vs. country)

`country` and `region` must be coherent: each country should map to its correct business region.

```python
region_country_map = df_seed.groupby("region")["country"].apply(list).to_dict()
synth_country = []
for region in synth_region:
    possible_countries = region_country_map.get(region, [])
    synth_country.append(rng.choice(possible_countries))
print(list(zip(synth_region[:10], synth_country[:10])))
# [('NA', 'United States'),
#  ('EMEA', 'Germany'),
#  ('EMEA', 'Germany'),
#  ('EMEA', 'Germany'),
#  ('LAD', 'Brazil'),
#  ('LAD', 'Argentina'),
#  ('NA', 'Canada'),
#  ('NA', 'Canada'),
#  ('JAPAC', 'Singapore'),
#  ('LAD', 'Argentina')]
```

### Joint distribution example (customer_net_worth | region)

Synthesize `customer_net_worth` values respecting the empirical joint distribution over `region`.

```python
demo_rows = pd.DataFrame({"region": synth_region})
synth_customer_net_worth = fake_joint_numerical(
    rng, df_seed, "customer_net_worth", ["region"], demo_rows
)
print(pd.Series(synth_customer_net_worth).describe())
# count    2.000000e+01
# mean     1.431880e+07
# std      2.174939e+07
# min      9.800000e+04
# 25%      4.050000e+05
# 50%      3.735000e+06
# 75%      2.600000e+07
# max      7.520000e+07
# dtype: float64
```

### Extrapolation (new values) example (customer_name)

Use *Faker* to synthesize new individual names or company names, even if not present in the seed.

```python
synth_customer_type = fake_categorical(rng, df_seed["customer_type"], size=n_synthesized)
synth_customer_name = [
    fake.name() if ct == "individual" else fake.company() for ct in synth_customer_type
]
print(synth_customer_name[:10])
# ['Norma Fisher',
#  'Sheppard-Tucker',
#  'Sandra Faulkner',
#  'Silva-Odonnell',
#  'Taylor, Taylor and Davis',
#  'Victoria Patel',
#  'Patrick, Barrera and Collins',
#  'Stephanie Sutton',
#  'Castro-Gomez',
#  'Martin Harris']
```

### Synthesizing remaining structured features according to property table

With each property demonstrated, now synthesize the remaining structured features as specified above.

```python
from wayflowcore.property import AnyProperty, IntegerProperty
from wayflowcore.steps import ToolExecutionStep
from wayflowcore.tools import ServerTool


def synthesize_structured_features(
    df_seed: pd.DataFrame, n_synthesized: int = 10, seed: int = 0
) -> pd.DataFrame:
    rng = np.random.default_rng(seed=seed)
    fake = Faker()
    fake.seed_instance(seed)
    synth_loan_reason = fake_categorical(rng, df_seed["loan_reason"], size=n_synthesized)
    synth_region_full = fake_categorical(rng, df_seed["region"], size=n_synthesized)
    synth_customer_type_full = fake_categorical(rng, df_seed["customer_type"], size=n_synthesized)
    region_country_map = df_seed.groupby("region")["country"].apply(list).to_dict()
    synth_country_full = []
    for region in synth_region_full:
        possible_countries = region_country_map.get(region, [])
        synth_country_full.append(rng.choice(possible_countries))
    synth_rows_for_joint = pd.DataFrame({"region": synth_region_full})
    synth_customer_net_worth_full = fake_joint_numerical(
        rng, df_seed, "customer_net_worth", ["region"], synth_rows_for_joint
    )
    synth_loan_value_full = fake_joint_numerical(
        rng, df_seed, "loan_value", ["region"], synth_rows_for_joint
    )
    synth_loan_proposed_interest_full = fake_joint_numerical(
        rng, df_seed, "loan_proposed_interest", ["region"], synth_rows_for_joint
    )
    synth_customer_name_full = [
        fake.name() if ct == "individual" else fake.company() for ct in synth_customer_type_full
    ]
    df_synthesized = pd.DataFrame(
        {
            "customer_type": synth_customer_type_full,
            "customer_name": synth_customer_name_full,
            "region": synth_region_full,
            "country": synth_country_full,
            "loan_reason": synth_loan_reason,
            "customer_net_worth": synth_customer_net_worth_full,
            "loan_value": synth_loan_value_full,
            "loan_proposed_interest": synth_loan_proposed_interest_full,
        }
    )
    return df_synthesized


def get_synthesize_structured_features_step() -> ToolExecutionStep:
    return ToolExecutionStep(
        tool=ServerTool(
            name="synthesize_structured_features",
            description="Synthesize all structured features",
            func=synthesize_structured_features,
            input_descriptors=[
                AnyProperty(name="df_seed"),
                IntegerProperty(name="n_synthesized", default_value=10),
                IntegerProperty(name="seed", default_value=0),
            ],
            output_descriptors=[AnyProperty(name="df_synthesized")],
        ),
        raise_exceptions=True,
    )


```

```python
from wayflowcore.flowhelpers import create_single_step_flow

flow = create_single_step_flow(step=get_synthesize_structured_features_step())
conv = flow.start_conversation(inputs={"df_seed": df_seed, "n_synthesized": 150, "seed": 0})
status = conv.execute()
df_synthesized = status.output_values["df_synthesized"]
print(df_synthesized)
```

## Verification: sanity checks and distribution comparison

Compare value counts and distributions for select features, and compare them to the original seed dataset.

```python
print("Synthesized region distribution:")
print(df_synthesized["region"].value_counts())
# Synthesized region distribution:
# JAPAC    46
# LAD      38
# EMEA     36
# NA       30
# Name: count, dtype: int64

print("\nSeed region distribution:")
print(df_seed["region"].value_counts())
# Seed region distribution:
# EMEA     3
# JAPAC    3
# NA       2
# LAD      2
# Name: count, dtype: int64
```

## Long text generation

To generate realistic business justifications for each record, you will use a language model (LLM) as part of your synthesis workflow. This section explains the configuration of the LLM, describes the prompts and parsing logic, outlines the flow definition, and demonstrates parallelized generation and validation.

### LLM selection and initialization

For long text generation, you need to use an LLM.
WayFlow supports several LLM providers. Select and configure your LLM below:




OCI GenAI

```python
from wayflowcore.models import OCIGenAIModel, OCIClientConfigWithApiKey

llm = OCIGenAIModel(
    model_id="provider.model-id",
    compartment_id="compartment-id",
    client_config=OCIClientConfigWithApiKey(
        service_endpoint="https://url-to-service-endpoint.com",
    ),
)
```

vLLM

```python
from wayflowcore.models import VllmModel

llm = VllmModel(
    model_id="model-id",
    host_port="VLLM_HOST_PORT",
)
```

Ollama

```python
from wayflowcore.models import OllamaModel

llm = OllamaModel(
    model_id="model-id",
)
```

### Prompt and I/O constants

Begin by defining the necessary output constants and prompts used to instruct the LLM and structure the flow:

```python

# Define I/O constants and step names
JUSTIFICATION_GEN_IO = "JUSTIFICATION_GEN_IO"
JUSTIFICATION_PARSING_IO = "JUSTIFICATION_PARSING_IO"
VALIDATION_IO = "VALIDATION_IO"
VALIDATION_PARSING_IO = "VALIDATION_PARSING_IO"

JUSTIFICATION_GEN_STEP = "JUSTIFICATION_GEN_STEP"
JUSTIFICATION_PARSING_STEP = "JUSTIFICATION_PARSING_STEP"
VALIDATION_STEP = "VALIDATION_STEP"
VALIDATION_PARSING_STEP = "VALIDATION_PARSING_STEP"

# Define prompts
JUSTIFICATION_PROMPT = """
## Context
You are an assistant that helps the business with loan applications.


## Task
Write a justification for a loan application, given certain customer data points.
The justification should be concise and detailed, and include all information that could be relevant for the loan application.
As an intermediate step before writing the justification, provide a reasoning section consisting of facts, arguments or any other relevant data that would help you with writing the justification.


## Example
Below is an example of the input data points and how they are structured, and an output justitifcation. Note that in this example the reasoning section has been omitted.

Customer: {{ seed_example['customer_name'] }} (type = {{ seed_example['customer_type'] }})
Location: {{ seed_example['region'] }}, {{ seed_example['country'] }}
Customer Net Worth: {{ seed_example['customer_net_worth'] }}
Loan: {{ seed_example['loan_value'] }} at {{ seed_example['loan_proposed_interest'] }} interest
Purpose: {{ seed_example['loan_reason'] }}

Justification: {{ seed_example['justification'] }}


## Data
Below are the input data points based on which you have to write the justification.

Customer: {{ generated_row['customer_name'] }} (type = {{ generated_row['customer_type'] }})
Location: {{ generated_row['region'] }}, {{ generated_row['country'] }}
Customer Net Worth: {{ generated_row['customer_net_worth'] }}
Loan: {{ generated_row['loan_value'] }} at {{ generated_row['loan_proposed_interest'] }} interest
Purpose: {{ generated_row['loan_reason'] }}


## Instructions
You must follow these guidelines:
- The tone, length and level of details in your justification are similarly aligned with the provided example
- The justification must be solely based on the provided data points
- The justification must be written around the `Purpose` data point
- The language should be professional and business-appropriate
- Include any specific financial details if relevant

The output must strictly follow the exactly format as below:
Reasoning: <fill this section with any facts or arguments relevant to the justification>
Justification: <fill this section with the justification>


## Output
""".strip()


VALIDATION_PROMPT = """
## Context
You are an assistant that helps the bank evaluate loan applications.


## Task
Evaluate the quality and plausibility of a loan justification against provided application data points of the customer.
The evaluation has to consider the following criteria:
1. Factual accuracy: All amounts, names, and details in the justification match the provided customer data points
2. Logical consistency: The reasoning aligns with customer profile and loan parameters
3. Realism: The justification is plausible for this type of loan application
4. Professional tone: The justification is written in business-appropriate language, and follows a coherent and logical structure
5. Completeness: The justification adequately addresses the loan reason and key factors


## Example
Below is an example of how the input data should look like. It starts with the customer data points and ends with the loan justification.

Customer: {{ seed_example['customer_name'] }} (type = {{ seed_example['customer_type'] }})
Location: {{ seed_example['region'] }}, {{ seed_example['country'] }}
Customer Net Worth: {{ seed_example['customer_net_worth'] }}
Loan: {{ seed_example['loan_value'] }} at {{ seed_example['loan_proposed_interest'] }} interest
Purpose: {{ seed_example['loan_reason'] }}

Justification: {{ seed_example['justification'] }}


## Data
Below is the input data for the current loan application you need to analyze.

Customer: {{ generated_row['customer_name'] }} (type = {{ generated_row['customer_type'] }})
Location: {{ generated_row['region'] }}, {{ generated_row['country'] }}
Customer Net Worth: {{ generated_row['customer_net_worth'] }}
Loan: {{ generated_row['loan_value'] }} at {{ generated_row['loan_proposed_interest']}} interest
Purpose: {{ generated_row['loan_reason'] }}

Justification: {{ justification }}


## Instructions
You must follow these guidelines:
- All evaluation criteria must be assessed
- Each evaluation criterion must be assessed solely based on the currently provided data points
- If a criterion cannot be confidently assessed based on the provided data points, say so
- Keep the evaluation reasoning short and concise

After all criteria have been assessed, you must end your answer with a verdict. The verdict must be in uppercase letters, and the list of possible verdicts and their formats is provided below:
- VALID (if the justification meets all evaluation criteria)
- INVALID: <reasoning> (if the justification fails any criteria, list them and provide short reasoning)
""".strip()
```

### Parsing functions

Parsing functions are responsible for extracting and normalizing the LLM outputs produced during justification and validation steps:

```python
def parse_cot_justification_output(llm_output: str) -> str:
    parts = llm_output.split("Justification:")
    if len(parts) < 2:
        return "Justification is not provided"
    return parts[1].strip()


def parse_validation_output(llm_output: str) -> bool:
    if "INVALID" in llm_output:
        return False
    elif "VALID" in llm_output:
        return True
    return False
```

### Justification generation flow definition

This flow defines a multi-step pipeline for generation, parsing, validation, and conditional retry of business justifications:

```python
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.models.llmgenerationconfig import LlmGenerationConfig
from wayflowcore.steps import CompleteStep, PromptExecutionStep, RetryStep


def get_justification_generation_step(llm: LlmModel) -> PromptExecutionStep:
    return PromptExecutionStep(
        prompt_template=JUSTIFICATION_PROMPT,
        llm=llm,
        generation_config=LlmGenerationConfig(max_tokens=2048),
        input_mapping={
            "seed_example": "seed_example",
            "generated_row": "generated_row",
        },
        output_mapping={PromptExecutionStep.OUTPUT: JUSTIFICATION_GEN_IO},
    )


def get_parse_justification_step() -> ToolExecutionStep:
    tool = ServerTool(
        name="parse_cot_justification_output",
        description="Parsing the specific LLM output of the justification generation step.",
        parameters={
            "llm_output": {
                "type": "string",
                "description": "Output from justification generation step.",
            }
        },
        func=parse_cot_justification_output,
        output={"type": "string"},
    )
    return ToolExecutionStep(
        tool=tool,
        input_mapping={"llm_output": JUSTIFICATION_GEN_IO},
        output_mapping={ToolExecutionStep.TOOL_OUTPUT: JUSTIFICATION_PARSING_IO},
    )


def get_validation_step(llm: LlmModel) -> PromptExecutionStep:
    return PromptExecutionStep(
        prompt_template=VALIDATION_PROMPT,
        llm=llm,
        generation_config=LlmGenerationConfig(max_tokens=2048),
        input_mapping={
            "seed_example": "seed_example",
            "generated_row": "generated_row",
            "justification": JUSTIFICATION_PARSING_IO,
        },
        output_mapping={PromptExecutionStep.OUTPUT: VALIDATION_IO},
    )


def get_parse_validation_step() -> ToolExecutionStep:
    tool = ServerTool(
        name="parse_validation_output",
        description="Parsing the specific LLM output of the validation step.",
        parameters={
            "llm_output": {
                "type": "string",
                "description": "Output from validation step.",
            }
        },
        func=parse_validation_output,
        output={"type": "bool"},
    )
    return ToolExecutionStep(
        tool=tool,
        input_mapping={"llm_output": VALIDATION_IO},
        output_mapping={ToolExecutionStep.TOOL_OUTPUT: VALIDATION_PARSING_IO},
    )


def get_retry_step(flow: Flow) -> RetryStep:
    return RetryStep(
        flow=flow,
        success_condition=VALIDATION_PARSING_IO,
        max_num_trials=3,
    )


def get_main_flow(llm_justification: LlmModel, llm_validation: LlmModel) -> Flow:
    justification_gen_step = get_justification_generation_step(llm_justification)
    justification_parse_step = get_parse_justification_step()
    validation_step = get_validation_step(llm_validation)
    validation_parse_step = get_parse_validation_step()

    return Flow.from_steps(
        steps=[justification_gen_step, justification_parse_step, validation_step, validation_parse_step],
        step_names=[JUSTIFICATION_GEN_STEP, JUSTIFICATION_PARSING_STEP, VALIDATION_STEP, VALIDATION_PARSING_STEP]
    )


def get_flow(llm_justification: LlmModel, llm_validation: LlmModel) -> Flow:
    main_flow = get_main_flow(llm_justification, llm_validation)
    retry_step = get_retry_step(main_flow)
    success_step = CompleteStep()
    failure_step = CompleteStep()

    return Flow(
        begin_step=retry_step,
        steps={
            "start": retry_step,
            "success": success_step,
            "failure": failure_step,
        },
        control_flow_edges=[
            ControlFlowEdge(
                source_step=retry_step,
                source_branch=retry_step.BRANCH_NEXT,
                destination_step=success_step,
            ),
            ControlFlowEdge(
                source_step=retry_step,
                source_branch=retry_step.BRANCH_FAILURE,
                destination_step=failure_step,
            ),
        ],
    )
```

### Batch justification generation and validation

Finally, apply the justification generation flow in parallel over your dataset using a MapStep (for more information see [How to Do Map and Reduce Operations in Flows](howto_mapstep.md)). This enables efficient batch generation and validation:

```python
from wayflowcore.property import ListProperty
from wayflowcore.steps import MapStep

flow = create_single_step_flow(
    step=MapStep(
        flow=get_flow(llm, llm),
        parallel_execution=True,
        unpack_input={
            "seed_example": ".seed_example",
            "generated_row": ".generated_row",
        },
        output_descriptors=[ListProperty(JUSTIFICATION_PARSING_IO)],
    )
)

input_sequence = [
    {
        "seed_example": df_seed.sample(n=1).iloc[0].to_dict(),
        "generated_row": row.to_dict(),
    }
    for _, row in df_synthesized.iterrows()
]
conversation = flow.start_conversation(inputs={MapStep.ITERATED_INPUT: input_sequence})
status = conversation.execute()
df_synthesized["justification"] = status.output_values[JUSTIFICATION_PARSING_IO]
```

## Synthetic dataset export

Save the synthesized dataset for downstream use.

```python
df_synthesized.to_json(file_path, orient="records", indent=4)
```

## Recap

This guide demonstrated property-respecting structured data synthesis, including logic for univariate, joint, interpolated, extrapolated, and coherent features. It also described long text generation and validation with a language model as a judge, including conditional retries. By following these workflows and recommendations, you can create realistic, flexible synthetic datasets to support your WayFlow projects.

## Next steps

Having learned how to synthesize data in WayFlow, you may now proceed to [How to Connect Assistants to Your Data](howto_datastores.md) to learn how to integrate your synthesized datasets with your assistants for downstream applications and enhanced testing.

## Full code

You can copy the full code for this guide below.

```python
# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# %%[markdown]
# WayFlow Code Example - How to Perform Data Synthesis
# ----------------------------------------------------

# How to use:
# Create a new Python virtual environment and install the latest WayFlow version.
# ```bash
# python -m venv venv-wayflowcore
# source venv-wayflowcore/bin/activate
# pip install --upgrade pip
# pip install "wayflowcore==26.1.1" 
# ```

# You can now run the script
# 1. As a Python file:
# ```bash
# python howto_data_synthesis.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.



# %%[markdown]
data:

# %%
import pandas as pd

seed_data = [
    {
        "customer_type": "organization",
        "customer_name": "Atlas Engineering Ltd.",
        "region": "EMEA",
        "country": "Germany",
        "customer_net_worth": 75200000,
        "loan_value": 12500000,
        "loan_proposed_interest": 4.9,
        "loan_reason": "Business expansion",
        "justification": "Atlas Engineering Ltd. seeks a $12,500,000 loan at a proposed 4.9% interest to expand its operations across the German automotive sector. With a robust net worth of $75,200,000 and a history of successful project delivery, the company is poised for growth. The expansion will create new jobs and increase market share, while our solid financials and collateral provide strong assurance. This aligns with our strategic business roadmap and justifies a favorable interest rate approval.",
    },
    {
        "customer_type": "individual",
        "customer_name": "Samantha Rivera",
        "region": "NA",
        "country": "United States",
        "customer_net_worth": 1580000,
        "loan_value": 80000,
        "loan_proposed_interest": 3.5,
        "loan_reason": "Home renovation",
        "justification": "Samantha Rivera requests a $80,000 loan at 3.5% interest to renovate her primary residence. With a net worth of $1,580,000 and stable income, Samantha’s credit profile is strong. The renovation will enhance her property value, reducing default risk. Given her responsible financial management and the secured nature of the loan, she is a low-risk borrower deserving of these favorable terms.",
    },
    {
        "customer_type": "organization",
        "customer_name": "MedicoPharma Solutions",
        "region": "JAPAC",
        "country": "Singapore",
        "customer_net_worth": 18500000,
        "loan_value": 4500000,
        "loan_proposed_interest": 5.7,
        "loan_reason": "Investment capital",
        "justification": "MedicoPharma Solutions applies for a $4,500,000 loan at a 5.7% rate to fund critical biotech investments. With a net worth of $18,500,000 and consistent year-over-year growth, the company demonstrates fiscal responsibility. The requested capital is earmarked for new laboratory equipment and R&D, supporting innovation and future revenue. The loan structure and interest rate are well-justified by the company's planned implementations and financial record.",
    },
    {
        "customer_type": "individual",
        "customer_name": "Rajeev Malhotra",
        "region": "JAPAC",
        "country": "India",
        "customer_net_worth": 280000,
        "loan_value": 42000,
        "loan_proposed_interest": 4.2,
        "loan_reason": "Education costs",
        "justification": "Rajeev Malhotra is seeking a $42,000 loan at 4.2% interest to pursue a postgraduate program in Bangalore. With a net worth of $280,000 and a stable employment history, Rajeev is committed to investing in his education for career advancement. The loan will cover tuition and related expenses, and his repayment plan is backed by projected post-graduation earnings, warranting an approval at this rate.",
    },
    {
        "customer_type": "organization",
        "customer_name": "Green Horizons Ltd.",
        "region": "LAD",
        "country": "Brazil",
        "customer_net_worth": 6270000,
        "loan_value": 1300000,
        "loan_proposed_interest": 5.2,
        "loan_reason": "Major appliance",
        "justification": "Green Horizons Ltd. is requesting a $1,300,000 loan with a 5.2% proposed interest rate to acquire industrial-scale solar panel systems for its new facility. With a net worth of $6,270,000, the organization’s history in sustainable development makes this investment logical. The equipment will reduce operational costs and support environmental commitments, providing a compelling rationale for loan approval.",
    },
    {
        "customer_type": "individual",
        "customer_name": "Lucia González",
        "region": "LAD",
        "country": "Argentina",
        "customer_net_worth": 98000,
        "loan_value": 19000,
        "loan_proposed_interest": 6.0,
        "loan_reason": "Debt consolidation",
        "justification": "Lucia González seeks a $19,000 loan at 6.0% interest to consolidate existing debts into a single manageable payment. With a net worth of $98,000 and steady monthly income, Lucia will benefit from simplified repayment terms and reduced overall interest expenses. Her disciplined repayment record supports the requested terms and merits consideration.",
    },
    {
        "customer_type": "organization",
        "customer_name": "BlueStar Trading GmbH",
        "region": "EMEA",
        "country": "Switzerland",
        "customer_net_worth": 26000000,
        "loan_value": 6200000,
        "loan_proposed_interest": 3.3,
        "loan_reason": "Vehicle purchase",
        "justification": "BlueStar Trading GmbH is applying for a $6,200,000 loan at 3.3% interest to upgrade its commercial vehicle fleet in Switzerland. Backed by a $26,000,000 net worth and healthy balance sheet, the acquisition will improve logistics and lower operational costs. Their creditworthiness and the use of vehicles as collateral minimize risk, justifying loan approval at this competitive rate.",
    },
    {
        "customer_type": "individual",
        "customer_name": "Fatima Al-Hassan",
        "region": "EMEA",
        "country": "United Arab Emirates",
        "customer_net_worth": 1200000,
        "loan_value": 38000,
        "loan_proposed_interest": 3.9,
        "loan_reason": "Vacation funding",
        "justification": "Fatima Al-Hassan requests a $38,000 loan at a 3.9% interest rate to cover a family vacation abroad. With a net worth of $1,200,000 and a solid credit score, she is well-positioned to repay the loan comfortably. Her responsible financial history further supports approval at the proposed rate for this short-term, purpose-specific loan.",
    },
    {
        "customer_type": "organization",
        "customer_name": "Aussie Urban Properties",
        "region": "JAPAC",
        "country": "Australia",
        "customer_net_worth": 51200000,
        "loan_value": 9700000,
        "loan_proposed_interest": 4.5,
        "loan_reason": "Business expansion",
        "justification": "Aussie Urban Properties seeks $9,700,000 in funding at a 4.5% interest rate to finance new residential developments in Sydney. With a net worth of $51,200,000 and proven experience in property management, the loan will be efficiently applied. The company’s past successes and robust financial health point to a strong ability to utilize and repay the loan as proposed.",
    },
    {
        "customer_type": "individual",
        "customer_name": "Jacob Peterson",
        "region": "NA",
        "country": "Canada",
        "customer_net_worth": 405000,
        "loan_value": 31000,
        "loan_proposed_interest": 2.7,
        "loan_reason": "Medical expenses",
        "justification": "Jacob Peterson is requesting a $31,000 loan at 2.7% interest to cover medical expenses resulting from an unexpected surgery. With a net worth of $405,000 and reliable employment, Jacob demonstrates strong repayment capacity. His consistent repayment track record and insurance partial coverage will mitigate lender risk, supporting approval at this attractive rate.",
    },
]

df_seed = pd.DataFrame(seed_data)
print(df_seed)


from typing import Any


# %%[markdown]
fake categorical:

# %%
import numpy as np


def fake_categorical(
    rng: np.random.Generator,
    pd_column: pd.Series,
    dropna: bool = False,
    **choice_kwargs: Any,
) -> Any:
    value_counts_dict = pd_column.value_counts(normalize=True, dropna=dropna).to_dict()
    categories = np.array(list(value_counts_dict.keys()))
    probabilities = np.array(list(value_counts_dict.values()))
    return rng.choice(categories, p=probabilities, **choice_kwargs)





# %%[markdown]
fake joint numerical:

# %%
def fake_joint_numerical(
    rng: np.random.Generator,
    df: pd.DataFrame,
    value_col: str,
    cat_cols: str | list[str],
    synthesized_rows: pd.DataFrame,
) -> list[Any]:
    result = []
    cat_array = (
        synthesized_rows[cat_cols].values
        if isinstance(cat_cols, list)
        else synthesized_rows[[cat_cols]].values
    )
    for cats in cat_array:
        mask = np.ones(len(df), dtype=bool)
        if isinstance(cat_cols, list):
            for col, val in zip(cat_cols, cats):
                mask &= df[col].values == val
        else:
            mask &= df[cat_cols].values == cats[0]
        matching_vals = df.loc[mask, value_col]
        if not matching_vals.empty:
            result.append(rng.choice(matching_vals))
        else:
            # Fallback: overall empirical
            result.append(rng.choice(df[value_col]))
    return result



import random


# %%[markdown]
seeds:

# %%
from faker import Faker

SEED = 0
rng = np.random.default_rng(SEED)
random.seed(SEED)
fake = Faker()
Faker.seed(SEED)


# %%[markdown]
generation configuration:

# %%
n_synthesized = 20  # adjust as needed


# %%[markdown]
univariate distribution:

# %%
synth_region = fake_categorical(rng, df_seed["region"], size=n_synthesized)
print(pd.Series(synth_region).value_counts())
# EMEA     7
# LAD      6
# NA       4
# JAPAC    3
# Name: count, dtype: int64


# %%[markdown]
coherency constraint:

# %%
region_country_map = df_seed.groupby("region")["country"].apply(list).to_dict()
synth_country = []
for region in synth_region:
    possible_countries = region_country_map.get(region, [])
    synth_country.append(rng.choice(possible_countries))
print(list(zip(synth_region[:10], synth_country[:10])))
# [('NA', 'United States'),
#  ('EMEA', 'Germany'),
#  ('EMEA', 'Germany'),
#  ('EMEA', 'Germany'),
#  ('LAD', 'Brazil'),
#  ('LAD', 'Argentina'),
#  ('NA', 'Canada'),
#  ('NA', 'Canada'),
#  ('JAPAC', 'Singapore'),
#  ('LAD', 'Argentina')]


# %%[markdown]
joint distribution:

# %%
demo_rows = pd.DataFrame({"region": synth_region})
synth_customer_net_worth = fake_joint_numerical(
    rng, df_seed, "customer_net_worth", ["region"], demo_rows
)
print(pd.Series(synth_customer_net_worth).describe())
# count    2.000000e+01
# mean     1.431880e+07
# std      2.174939e+07
# min      9.800000e+04
# 25%      4.050000e+05
# 50%      3.735000e+06
# 75%      2.600000e+07
# max      7.520000e+07
# dtype: float64


# %%[markdown]
extrapolation:

# %%
synth_customer_type = fake_categorical(rng, df_seed["customer_type"], size=n_synthesized)
synth_customer_name = [
    fake.name() if ct == "individual" else fake.company() for ct in synth_customer_type
]
print(synth_customer_name[:10])
# ['Norma Fisher',
#  'Sheppard-Tucker',
#  'Sandra Faulkner',
#  'Silva-Odonnell',
#  'Taylor, Taylor and Davis',
#  'Victoria Patel',
#  'Patrick, Barrera and Collins',
#  'Stephanie Sutton',
#  'Castro-Gomez',
#  'Martin Harris']



# %%[markdown]
full synthesis:

# %%
from wayflowcore.property import AnyProperty, IntegerProperty
from wayflowcore.steps import ToolExecutionStep
from wayflowcore.tools import ServerTool


def synthesize_structured_features(
    df_seed: pd.DataFrame, n_synthesized: int = 10, seed: int = 0
) -> pd.DataFrame:
    rng = np.random.default_rng(seed=seed)
    fake = Faker()
    fake.seed_instance(seed)
    synth_loan_reason = fake_categorical(rng, df_seed["loan_reason"], size=n_synthesized)
    synth_region_full = fake_categorical(rng, df_seed["region"], size=n_synthesized)
    synth_customer_type_full = fake_categorical(rng, df_seed["customer_type"], size=n_synthesized)
    region_country_map = df_seed.groupby("region")["country"].apply(list).to_dict()
    synth_country_full = []
    for region in synth_region_full:
        possible_countries = region_country_map.get(region, [])
        synth_country_full.append(rng.choice(possible_countries))
    synth_rows_for_joint = pd.DataFrame({"region": synth_region_full})
    synth_customer_net_worth_full = fake_joint_numerical(
        rng, df_seed, "customer_net_worth", ["region"], synth_rows_for_joint
    )
    synth_loan_value_full = fake_joint_numerical(
        rng, df_seed, "loan_value", ["region"], synth_rows_for_joint
    )
    synth_loan_proposed_interest_full = fake_joint_numerical(
        rng, df_seed, "loan_proposed_interest", ["region"], synth_rows_for_joint
    )
    synth_customer_name_full = [
        fake.name() if ct == "individual" else fake.company() for ct in synth_customer_type_full
    ]
    df_synthesized = pd.DataFrame(
        {
            "customer_type": synth_customer_type_full,
            "customer_name": synth_customer_name_full,
            "region": synth_region_full,
            "country": synth_country_full,
            "loan_reason": synth_loan_reason,
            "customer_net_worth": synth_customer_net_worth_full,
            "loan_value": synth_loan_value_full,
            "loan_proposed_interest": synth_loan_proposed_interest_full,
        }
    )
    return df_synthesized


def get_synthesize_structured_features_step() -> ToolExecutionStep:
    return ToolExecutionStep(
        tool=ServerTool(
            name="synthesize_structured_features",
            description="Synthesize all structured features",
            func=synthesize_structured_features,
            input_descriptors=[
                AnyProperty(name="df_seed"),
                IntegerProperty(name="n_synthesized", default_value=10),
                IntegerProperty(name="seed", default_value=0),
            ],
            output_descriptors=[AnyProperty(name="df_synthesized")],
        ),
        raise_exceptions=True,
    )




# %%[markdown]
full synthesis flow:

# %%
from wayflowcore.flowhelpers import create_single_step_flow

flow = create_single_step_flow(step=get_synthesize_structured_features_step())
conv = flow.start_conversation(inputs={"df_seed": df_seed, "n_synthesized": 150, "seed": 0})
status = conv.execute()
df_synthesized = status.output_values["df_synthesized"]
print(df_synthesized)


# %%[markdown]
verification:

# %%
print("Synthesized region distribution:")
print(df_synthesized["region"].value_counts())
# Synthesized region distribution:
# JAPAC    46
# LAD      38
# EMEA     36
# NA       30
# Name: count, dtype: int64

print("\nSeed region distribution:")
print(df_seed["region"].value_counts())
# Seed region distribution:
# EMEA     3
# JAPAC    3
# NA       2
# LAD      2
# Name: count, dtype: int64


# %%[markdown]
long text generation:

# %%

# Define I/O constants and step names
JUSTIFICATION_GEN_IO = "JUSTIFICATION_GEN_IO"
JUSTIFICATION_PARSING_IO = "JUSTIFICATION_PARSING_IO"
VALIDATION_IO = "VALIDATION_IO"
VALIDATION_PARSING_IO = "VALIDATION_PARSING_IO"

JUSTIFICATION_GEN_STEP = "JUSTIFICATION_GEN_STEP"
JUSTIFICATION_PARSING_STEP = "JUSTIFICATION_PARSING_STEP"
VALIDATION_STEP = "VALIDATION_STEP"
VALIDATION_PARSING_STEP = "VALIDATION_PARSING_STEP"

# Define prompts
JUSTIFICATION_PROMPT = """
## Context
You are an assistant that helps the business with loan applications.


## Task
Write a justification for a loan application, given certain customer data points.
The justification should be concise and detailed, and include all information that could be relevant for the loan application.
As an intermediate step before writing the justification, provide a reasoning section consisting of facts, arguments or any other relevant data that would help you with writing the justification.


## Example
Below is an example of the input data points and how they are structured, and an output justitifcation. Note that in this example the reasoning section has been omitted.

Customer: {{ seed_example['customer_name'] }} (type = {{ seed_example['customer_type'] }})
Location: {{ seed_example['region'] }}, {{ seed_example['country'] }}
Customer Net Worth: {{ seed_example['customer_net_worth'] }}
Loan: {{ seed_example['loan_value'] }} at {{ seed_example['loan_proposed_interest'] }} interest
Purpose: {{ seed_example['loan_reason'] }}

Justification: {{ seed_example['justification'] }}


## Data
Below are the input data points based on which you have to write the justification.

Customer: {{ generated_row['customer_name'] }} (type = {{ generated_row['customer_type'] }})
Location: {{ generated_row['region'] }}, {{ generated_row['country'] }}
Customer Net Worth: {{ generated_row['customer_net_worth'] }}
Loan: {{ generated_row['loan_value'] }} at {{ generated_row['loan_proposed_interest'] }} interest
Purpose: {{ generated_row['loan_reason'] }}


## Instructions
You must follow these guidelines:
- The tone, length and level of details in your justification are similarly aligned with the provided example
- The justification must be solely based on the provided data points
- The justification must be written around the `Purpose` data point
- The language should be professional and business-appropriate
- Include any specific financial details if relevant

The output must strictly follow the exactly format as below:
Reasoning: <fill this section with any facts or arguments relevant to the justification>
Justification: <fill this section with the justification>


## Output
""".strip()


VALIDATION_PROMPT = """
## Context
You are an assistant that helps the bank evaluate loan applications.


## Task
Evaluate the quality and plausibility of a loan justification against provided application data points of the customer.
The evaluation has to consider the following criteria:
1. Factual accuracy: All amounts, names, and details in the justification match the provided customer data points
2. Logical consistency: The reasoning aligns with customer profile and loan parameters
3. Realism: The justification is plausible for this type of loan application
4. Professional tone: The justification is written in business-appropriate language, and follows a coherent and logical structure
5. Completeness: The justification adequately addresses the loan reason and key factors


## Example
Below is an example of how the input data should look like. It starts with the customer data points and ends with the loan justification.

Customer: {{ seed_example['customer_name'] }} (type = {{ seed_example['customer_type'] }})
Location: {{ seed_example['region'] }}, {{ seed_example['country'] }}
Customer Net Worth: {{ seed_example['customer_net_worth'] }}
Loan: {{ seed_example['loan_value'] }} at {{ seed_example['loan_proposed_interest'] }} interest
Purpose: {{ seed_example['loan_reason'] }}

Justification: {{ seed_example['justification'] }}


## Data
Below is the input data for the current loan application you need to analyze.

Customer: {{ generated_row['customer_name'] }} (type = {{ generated_row['customer_type'] }})
Location: {{ generated_row['region'] }}, {{ generated_row['country'] }}
Customer Net Worth: {{ generated_row['customer_net_worth'] }}
Loan: {{ generated_row['loan_value'] }} at {{ generated_row['loan_proposed_interest']}} interest
Purpose: {{ generated_row['loan_reason'] }}

Justification: {{ justification }}


## Instructions
You must follow these guidelines:
- All evaluation criteria must be assessed
- Each evaluation criterion must be assessed solely based on the currently provided data points
- If a criterion cannot be confidently assessed based on the provided data points, say so
- Keep the evaluation reasoning short and concise

After all criteria have been assessed, you must end your answer with a verdict. The verdict must be in uppercase letters, and the list of possible verdicts and their formats is provided below:
- VALID (if the justification meets all evaluation criteria)
- INVALID: <reasoning> (if the justification fails any criteria, list them and provide short reasoning)
""".strip()



# %%[markdown]
parsing functions:

# %%
def parse_cot_justification_output(llm_output: str) -> str:
    parts = llm_output.split("Justification:")
    if len(parts) < 2:
        return "Justification is not provided"
    return parts[1].strip()


def parse_validation_output(llm_output: str) -> bool:
    if "INVALID" in llm_output:
        return False
    elif "VALID" in llm_output:
        return True
    return False


from wayflowcore.flow import Flow
from wayflowcore.models import LlmModel


# %%[markdown]
justification generation flow:

# %%
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.models.llmgenerationconfig import LlmGenerationConfig
from wayflowcore.steps import CompleteStep, PromptExecutionStep, RetryStep


def get_justification_generation_step(llm: LlmModel) -> PromptExecutionStep:
    return PromptExecutionStep(
        prompt_template=JUSTIFICATION_PROMPT,
        llm=llm,
        generation_config=LlmGenerationConfig(max_tokens=2048),
        input_mapping={
            "seed_example": "seed_example",
            "generated_row": "generated_row",
        },
        output_mapping={PromptExecutionStep.OUTPUT: JUSTIFICATION_GEN_IO},
    )


def get_parse_justification_step() -> ToolExecutionStep:
    tool = ServerTool(
        name="parse_cot_justification_output",
        description="Parsing the specific LLM output of the justification generation step.",
        parameters={
            "llm_output": {
                "type": "string",
                "description": "Output from justification generation step.",
            }
        },
        func=parse_cot_justification_output,
        output={"type": "string"},
    )
    return ToolExecutionStep(
        tool=tool,
        input_mapping={"llm_output": JUSTIFICATION_GEN_IO},
        output_mapping={ToolExecutionStep.TOOL_OUTPUT: JUSTIFICATION_PARSING_IO},
    )


def get_validation_step(llm: LlmModel) -> PromptExecutionStep:
    return PromptExecutionStep(
        prompt_template=VALIDATION_PROMPT,
        llm=llm,
        generation_config=LlmGenerationConfig(max_tokens=2048),
        input_mapping={
            "seed_example": "seed_example",
            "generated_row": "generated_row",
            "justification": JUSTIFICATION_PARSING_IO,
        },
        output_mapping={PromptExecutionStep.OUTPUT: VALIDATION_IO},
    )


def get_parse_validation_step() -> ToolExecutionStep:
    tool = ServerTool(
        name="parse_validation_output",
        description="Parsing the specific LLM output of the validation step.",
        parameters={
            "llm_output": {
                "type": "string",
                "description": "Output from validation step.",
            }
        },
        func=parse_validation_output,
        output={"type": "bool"},
    )
    return ToolExecutionStep(
        tool=tool,
        input_mapping={"llm_output": VALIDATION_IO},
        output_mapping={ToolExecutionStep.TOOL_OUTPUT: VALIDATION_PARSING_IO},
    )


def get_retry_step(flow: Flow) -> RetryStep:
    return RetryStep(
        flow=flow,
        success_condition=VALIDATION_PARSING_IO,
        max_num_trials=3,
    )


def get_main_flow(llm_justification: LlmModel, llm_validation: LlmModel) -> Flow:
    justification_gen_step = get_justification_generation_step(llm_justification)
    justification_parse_step = get_parse_justification_step()
    validation_step = get_validation_step(llm_validation)
    validation_parse_step = get_parse_validation_step()

    return Flow.from_steps(
        steps=[justification_gen_step, justification_parse_step, validation_step, validation_parse_step],
        step_names=[JUSTIFICATION_GEN_STEP, JUSTIFICATION_PARSING_STEP, VALIDATION_STEP, VALIDATION_PARSING_STEP]
    )


def get_flow(llm_justification: LlmModel, llm_validation: LlmModel) -> Flow:
    main_flow = get_main_flow(llm_justification, llm_validation)
    retry_step = get_retry_step(main_flow)
    success_step = CompleteStep()
    failure_step = CompleteStep()

    return Flow(
        begin_step=retry_step,
        steps={
            "start": retry_step,
            "success": success_step,
            "failure": failure_step,
        },
        control_flow_edges=[
            ControlFlowEdge(
                source_step=retry_step,
                source_branch=retry_step.BRANCH_NEXT,
                destination_step=success_step,
            ),
            ControlFlowEdge(
                source_step=retry_step,
                source_branch=retry_step.BRANCH_FAILURE,
                destination_step=failure_step,
            ),
        ],
    )


# %%[markdown]
llm definition:

# %%
from wayflowcore.models import VllmModel

llm = VllmModel(
    model_id="LLAMA_MODEL_ID",
    host_port="LLAMA_API_URL",
)


# %%[markdown]
justification generation:

# %%
from wayflowcore.property import ListProperty
from wayflowcore.steps import MapStep

flow = create_single_step_flow(
    step=MapStep(
        flow=get_flow(llm, llm),
        parallel_execution=True,
        unpack_input={
            "seed_example": ".seed_example",
            "generated_row": ".generated_row",
        },
        output_descriptors=[ListProperty(JUSTIFICATION_PARSING_IO)],
    )
)

input_sequence = [
    {
        "seed_example": df_seed.sample(n=1).iloc[0].to_dict(),
        "generated_row": row.to_dict(),
    }
    for _, row in df_synthesized.iterrows()
]
conversation = flow.start_conversation(inputs={MapStep.ITERATED_INPUT: input_sequence})
status = conversation.execute()
df_synthesized["justification"] = status.output_values[JUSTIFICATION_PARSING_IO]



# %%[markdown]
exporting synthetic dataset:

# %%
df_synthesized.to_json(file_path, orient="records", indent=4)
```

| Feature                | Type   | Interp./Extrap.   | Method or constraint                                                                 | Distribution target             |
|------------------------|--------|-------------------|--------------------------------------------------------------------------------------|---------------------------------|
| customer_type          | cat    | Interpolation     | Sampled with empirical (seed) univariate
distribution                            | Preserve univariate             |
| customer_name          | string | Extrapolation     | Use `fake.name()` if individual, else
`fake.company()`                           | /                               |
| region                 | cat    | Interpolation     | Choice among [EMEA, JAPAC, LAD, NA]                                                  | /                               |
| country                | cat    | Interpolation     | Based on mapping from region; randomly
select among possible countries in region | Coherency: region               |
| customer_net_worth     | num    | Interpolation     | Sampled from joint empirical distribution
with region                            | Joint: region                   |
| loan_value             | num    | Interpolation     | Sampled from joint empirical distribution
with region                            | Joint: region                   |
| loan_proposed_interest | num    | Interpolation     | Sampled from joint empirical distribution
with region                            | Joint: region                   |
| loan_reason            | cat    | Interpolation     | Sampled with empirical (seed) univariate
distribution                            | Preserve univariate             |
| justification          | string | Extrapolation     | Long text generation                                                                 | Coherency with other
fields |
