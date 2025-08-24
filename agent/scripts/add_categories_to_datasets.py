#!/usr/bin/env python3
"""
Script to add categories to each dataset in the statvar_imports_config.json file
"""

import json
import os

# Define category mappings for each dataset
DATASET_CATEGORIES = {
    "zurich_bev_4031_sex_wiki": {
        "main_categories": ["Demographics"],
        "geographic_level": "City/Metro",
        "time_period": "Time series",
        "data_source": "Administrative"
    },
    "zurich_bev_4031_wiki": {
        "main_categories": ["Demographics"],
        "geographic_level": "City/Metro",
        "time_period": "Time series",
        "data_source": "Administrative"
    },
    "zurich_bev_4031_hel_wik": {
        "main_categories": ["Demographics"],
        "geographic_level": "City/Metro",
        "time_period": "Time series",
        "data_source": "Administrative"
    },
    "us_bls_bls_ces": {
        "main_categories": ["Economy"],
        "subcategories": ["Employment", "Wages"],
        "geographic_level": "National",
        "time_period": "Monthly",
        "data_source": "Administrative"
    },
    "us_bls_bls_ces_state": {
        "main_categories": ["Economy"],
        "subcategories": ["Employment", "Wages"],
        "geographic_level": "State",
        "time_period": "Monthly",
        "data_source": "Administrative"
    },
    "bis_bis_central_bank_policy_rate": {
        "main_categories": ["Economy"],
        "subcategories": ["Interest rates", "Monetary policy"],
        "geographic_level": "National",
        "time_period": "Time series",
        "data_source": "Administrative"
    },
    "us_census_us_monthly_retail_sales": {
        "main_categories": ["Economy"],
        "subcategories": ["Retail", "Trade"],
        "geographic_level": "National",
        "time_period": "Monthly",
        "data_source": "Census/Survey"
    },
    "us_hbcu_data_nces_hbcu_enrollment_import": {
        "main_categories": ["Education"],
        "subcategories": ["Higher education", "Enrollment"],
        "geographic_level": "National",
        "time_period": "Annual",
        "data_source": "Administrative"
    },
    "world_bank_worldbank_ids": {
        "main_categories": ["Economy"],
        "subcategories": ["Debt", "International finance"],
        "geographic_level": "National",
        "time_period": "Annual",
        "data_source": "Administrative"
    },
    "world_bank_commodity_market": {
        "main_categories": ["Economy"],
        "subcategories": ["Commodity prices", "Markets"],
        "geographic_level": "National",
        "time_period": "Monthly",
        "data_source": "Administrative"
    },
    "usa_dol_minimum_wage": {
        "main_categories": ["Economy"],
        "subcategories": ["Wages", "Labor"],
        "geographic_level": "State",
        "time_period": "Annual",
        "data_source": "Administrative"
    },
    "us_federal_reserve_h15_interest_rates_us_federal_rates": {
        "main_categories": ["Economy"],
        "subcategories": ["Interest rates", "Monetary policy"],
        "geographic_level": "National",
        "time_period": "Time series",
        "data_source": "Administrative"
    },
    "undata": {
        "main_categories": ["Demographics"],
        "subcategories": ["Population", "Urban/Rural"],
        "geographic_level": "National",
        "time_period": "Annual",
        "data_source": "Census/Survey"
    },
    "fao_currency_and_exchange_rate_fao_currency_statvar": {
        "main_categories": ["Economy"],
        "subcategories": ["Exchange rates", "Currency"],
        "geographic_level": "National",
        "time_period": "Annual",
        "data_source": "Administrative"
    },
    "mexico_subnational_population_statistics_mexico_census_aa2": {
        "main_categories": ["Demographics"],
        "subcategories": ["Population", "Age", "Gender"],
        "geographic_level": "County",
        "time_period": "Annual",
        "data_source": "Census/Survey"
    },
    "brazil_visdata_FoodBasketDistribution": {
        "main_categories": ["Agriculture", "Health"],
        "subcategories": ["Food security", "Social welfare"],
        "geographic_level": "County",
        "time_period": "Time series",
        "data_source": "Administrative"
    },
    "fbi_fbigovcrime": {
        "main_categories": ["Crime"],
        "subcategories": ["Crime incidents", "Law enforcement"],
        "geographic_level": "State",
        "time_period": "Annual",
        "data_source": "Administrative"
    },
    "uae_bayanat_uae_population": {
        "main_categories": ["Demographics"],
        "subcategories": ["Population", "Gender", "Nationality"],
        "geographic_level": "State",
        "time_period": "Annual",
        "data_source": "Administrative"
    },
    "statistics_new_zealand_new_zealand_census": {
        "main_categories": ["Demographics", "Health"],
        "subcategories": ["Population", "Healthcare"],
        "geographic_level": "National",
        "time_period": "Annual",
        "data_source": "Census/Survey"
    },
    "opendataforafrica_rwanda_census": {
        "main_categories": ["Demographics", "Economy", "Education"],
        "subcategories": ["Population", "Employment", "Schools"],
        "geographic_level": "County",
        "time_period": "Annual",
        "data_source": "Census/Survey"
    },
    "opendataforafrica_kenya_census": {
        "main_categories": ["Demographics", "Health", "Education"],
        "subcategories": ["Population", "Healthcare", "Schools"],
        "geographic_level": "County",
        "time_period": "Annual",
        "data_source": "Census/Survey"
    },
    "ireland_census": {
        "main_categories": ["Demographics", "Health", "Economy"],
        "subcategories": ["Population", "Mortality", "Employment"],
        "geographic_level": "County",
        "time_period": "Annual",
        "data_source": "Census/Survey"
    }
}

def add_categories_to_config(input_file, output_file):
    """Add categories to each dataset in the config file"""
    
    # Read the existing config
    with open(input_file, 'r') as f:
        config = json.load(f)
    
    # Add categories to each dataset
    for dataset_id, dataset_info in config['imports'].items():
        if dataset_id in DATASET_CATEGORIES:
            dataset_info['categories'] = DATASET_CATEGORIES[dataset_id]
        else:
            # Default categories if not explicitly mapped
            dataset_info['categories'] = {
                "main_categories": ["Uncategorized"],
                "geographic_level": "Unknown",
                "time_period": "Unknown",
                "data_source": "Unknown"
            }
    
    # Write the updated config
    with open(output_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"Successfully added categories to {len(config['imports'])} datasets")
    print(f"Output saved to: {output_file}")

if __name__ == "__main__":
    input_file = "/Users/rohit/Documents/github/rohitkumarbhagat/data/statvar_imports_config.json"
    output_file = "/Users/rohit/Documents/github/rohitkumarbhagat/data/statvar_imports_config_with_categories.json"
    
    add_categories_to_config(input_file, output_file)