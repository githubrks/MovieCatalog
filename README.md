# Movie Catalog - Udacity's nano degree fullstack program project

This is a simple catalog app built with Python, Flask and SQLAlchemy. The app supports user authentication and authorization using OAuth 2.0 and Google Login API.
Logged in users can add movie categories and new movies, as well as edit, delete movies that they have created. Users who are not logged in can view the contents of the movie catalog but cannot make changes.


## Tools Required
- [Vagrant](https://www.vagrantup.com/)
- [Udacity Vagrantfile](https://github.com/udacity/fullstack-nanodegree-vm)
- [VirtualBox](https://www.virtualbox.org/wiki/Downloads)

## Installation

- Install Vagrant and VirtualBox
- Clone the Vagrantfile from the Udacity Repo
- Copy and unzip the files into the `catalog/` directory found in the Vagrant directory
- Run `vagrant up` to run the virtual machine, then `vagrant ssh` to login to the VM
- Use pip to install Pipenv `pip install --user pipenv`
- CD to the catalog project directory `cd \vagrant\catalog`
- from the main directory run `pipenv install -r requirements`
- run application with `python application.py` from within its directory
- go to `http://localhost:8000` to access the application
- *moviecatalog db has few initial movies added which can be viewed without login.

## JSON Endpoints

`/catalog.json` - Returns JSON of all movies in catalog

`/categories/<int:category_id>/item/<int:catalog_item_id>/JSON` - Returns JSON of selected movie in catalog

`/categories/JSON` - Returns JSON of all movie categories in catalog


## Authors

* **Ravi Singh** - (https://github.com/githubrks)


## Acknowledgments

* This project is based on the templates and sample provied by Udacity course for Restaurent Menu app. 

