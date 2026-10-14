# Object-Oriented Programming Assignment 2

## Student details
- Name: NUWARINDA ROSELINE
- Access Number: B38638
- Student Number:S26M19/017


## About the assignment
This assignment focused on applying object-oriented programming principles to solve real-world problems in Python. The repository contains two mini-projects:

- A weather forecast application that fetches and processes location and forecast data.
- A Uganda tax engine that calculates tax values using business rules and validation logic.

The goal was to design reusable classes and functions, structure the project logically, and test the code to ensure correctness and reliability.

## Key findings
- The weather project showed how API responses can be validated, parsed, and handled safely when data is missing or invalid.
- The tax engine demonstrated how rules such as PAYE, VAT, and corporate tax can be modelled in a clear and maintainable way.
- Testing is essential in OOP projects because edge cases and boundary values often reveal logic errors that are not obvious during implementation.
- Reusable design helps reduce duplication and makes it easier to extend the system in the future.

## Setup
To run this project locally, use the following commands in PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

After installation, open the notebooks in VS Code and run them from the project environment:

- `project1_weather.ipynb`
- `project2_tax_engine.ipynb`

## Tests
The project includes unit tests that validate the main logic and catch common errors.

```powershell
python -m unittest discover -s tests -v
```

These tests cover:
- input validation
- calculation correctness
- error handling
- boundary conditions
- expected behavior for invalid or incomplete data

## AI usage
AI tools were used to support this assignment in the following ways:

- Action workflow, this README and project documentation
- helping debug test failures and edge cases
- improving the structure and clarity of the README and project explanation

AI-generated suggestions were reviewed and adjusted before being used in the final work.

## Summary
This assignment helped strengthen understanding of object-oriented design, modular code structure, testing practices, and practical problem solving in Python. The final project demonstrates both technical implementation and a disciplined approach to validation and debugging.