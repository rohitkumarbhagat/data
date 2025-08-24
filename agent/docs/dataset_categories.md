# Dataset Categories for Classification

## Main Categories

1. **Demographics** - Population, age, gender, race, ethnicity, citizenship, migration
2. **Economy** - Employment, income, poverty, business, trade, prices
3. **Health** - Disease, mortality, healthcare access, medical conditions, vaccines
4. **Education** - Enrollment, attainment, schools, teachers, students
5. **Housing** - Housing units, home values, rents, occupancy, housing conditions
6. **Environment** - Air quality, water, climate, emissions, natural disasters
7. **Energy** - Electricity, fuel, renewable energy, consumption
8. **Agriculture** - Farms, crops, livestock, food production
9. **Crime** - Crime incidents, law enforcement, incarceration
10. **Transportation** - Commute, vehicles, transport modes

## Additional Attributes

### Geographic Levels
- National
- State
- County
- City/Metro
- Census Tract

### Time Periods
- Annual
- Monthly
- Point-in-time
- Time series

### Data Sources
- Census/Survey
- Administrative
- Satellite/Sensor
- Crowdsourced

## Usage Notes

Each dataset should be tagged with:
- 1-3 main categories (primary category first)
- Geographic level
- Time period type
- Data source type

For similarity search, datasets sharing the same main categories are considered most similar, with additional matching on geographic level and time period adding to the similarity score.