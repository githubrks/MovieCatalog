#!/usr/bin/env python3
# This modules contains all the routes of the application.

from flask import Flask, render_template, request, redirect, jsonify
from flask import url_for, flash, make_response
from flask import session as login_session
from sqlalchemy import create_engine, asc
from sqlalchemy.orm import sessionmaker
from database_setup import Base, CatalogItem, Category, User
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
from functools import wraps
import random
import string
import httplib2
import json
import requests


app = Flask(__name__)

CLIENT_ID = json.loads(
    open('client_secret.json', 'r').read())['web']['client_id']

engine = create_engine('sqlite:///moviecatalog.db',
                       connect_args={'check_same_thread': False})
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()


# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in login_session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


# User Login and Session Handling

# Login route, create anit-forgery state token
@app.route('/login')
def login():
    state = ''.join(
        random.choice(
            string.ascii_uppercase + string.digits) for x in xrange(32))
    login_session['state'] = state
    return render_template('login.html', STATE=state)


# CONNECT - Google login get token
@app.route('/gconnect', methods=['POST'])
def gconnect():
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    code = request.data

    try:
        oauth_flow = flow_from_clientsecrets('client_secret.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v3/tokeninfo?access_token=%s'
           % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response

    gplus_id = credentials.id_token['sub']
    if result['sub'] != gplus_id:
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    if result['aud'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_credentials = login_session.get('credentials')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_credentials is not None and gplus_id == stored_gplus_id:
        response = make_response(
            json.dumps('Current user is already connected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    login_session['access_token'] = credentials.to_json()
    login_session['gplus_id'] = gplus_id

    userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    login_session['provider'] = 'google'
    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']

    user_id = getUserID(login_session['email'])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ''' " style = "width: 200px; height: 200px;border-radius: 150px;
    -webkit-border-radius: 150px;-moz-border-radius: 150px;"> '''
    flash("you are now logged in as %s" % login_session['username'], 'success')
    return output


# DISCONNECT - reset user login_session


@app.route('/disconnect')
def disconnect():
    if 'provider' in login_session:
        if login_session['provider'] == 'google':
            gdisconnect()
            if 'gplus_id' in login_session:
                del login_session['gplus_id']
            if 'credentials' in login_session:
                del login_session['credentials']
        if 'username' in login_session:
            del login_session['username']
        if 'email' in login_session:
            del login_session['email']
        if 'picture' in login_session:
            del login_session['picture']
        if 'user_id' in login_session:
            del login_session['user_id']
        del login_session['provider']
        flash("You have been logged out successfully.", 'success')
        return redirect(url_for('showMovieCatalog'))
    else:
        flash("You were not logged in", 'danger')
        return redirect(url_for('showMovieCatalog'))


@app.route('/gdisconnect')
def gdisconnect():
    credentials = login_session.get('credentials')
    if credentials is None:
        response = make_response(json.dumps('Current user not connected.'),
                                 401)
        response.headers['Content-type'] = 'application/json'
        return response
    access_token = credentials.access_token
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % access_token
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]

    if result['status'] == '200':
        del login_session['username']
        del login_session['email']
        del login_session['picture']
        del login_session['credentials']
        del login_session['gplus_id']

        response = make_response(json.dumps('Successfully Logged-Out.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    else:
        response = make_response(
            json.dumps('Failed to revoke token for user.'), 400)
        response.headers['Content-Type'] = 'application/json'
        return response


# CRUD for categories
@app.route('/')
@app.route('/categories/')
def showMovieCatalog():
    """Returns page with all movie categories and recently added items"""
    categories = session.query(Category).all()
    items = session.query(CatalogItem).order_by(CatalogItem.id.desc())
    quantity = items.count()
    if 'username' not in login_session:
        return render_template(
            'public_movie_catalog.html',
            categories=categories, items=items, quantity=quantity)
    else:
        return render_template(
            'movie_catalog.html',
            categories=categories, items=items, quantity=quantity)


# CREATE - New movie category
@app.route('/categories/new', methods=['GET', 'POST'])
@login_required
def newMovieCategory():
    """Allows user to create new movie category"""
    if request.method == 'POST':
        if 'user_id' not in login_session and 'email' in login_session:
            login_session['user_id'] = getUserID(login_session['email'])
        newCategory = Category(
            name=request.form['name'],
            user_id=login_session['user_id'])
        session.add(newCategory)
        session.commit()
        flash("New movie category created!", 'success')
        return redirect(url_for('showMovieCatalog'))
    else:
        return render_template('new_movie_category.html')


# EDIT a movie category
@app.route('/categories/<int:category_id>/edit/', methods=['GET', 'POST'])
@login_required
def editMovieCategory(category_id):
    """Allows user to edit an existing movie category"""
    editedCategory = session.query(Category).filter_by(id=category_id).one()
    if editedCategory.user_id != login_session['user_id']:
        return """<script>function myFunction()
        {alert('You are not authorized!')}
        </script><body onload='myFunction()'>"""
    if request.method == 'POST':
        if request.form['name']:
            editedCategory.name = request.form['name']
            flash('Movie category Successfully Edited %s'
                  % editedCategory.name, 'success')
            return redirect(url_for('showMovieCatalog'))
    else:
        return render_template('edit_movie_category.html',
                               category=editedCategory)


# DELETE a movie category
@app.route('/categories/<int:category_id>/delete/', methods=['GET', 'POST'])
@login_required
def deleteMovieCategory(category_id):
    """Allows user to delete an existing movie category"""
    categoryToDelete = session.query(Category).filter_by(id=category_id).one()
    if categoryToDelete.user_id != login_session['user_id']:
        return """<script>function myFunction()
        {alert('You are not authorized!')}
        </script><body onload='myFunction()'>"""
    if request.method == 'POST':
        session.delete(categoryToDelete)
        flash('Movie catagory %s has been Successfully Deleted'
              % categoryToDelete.name, 'success')
        session.commit()
        return redirect(url_for('showMovieCatalog', category_id=category_id))
    else:
        return render_template('delete_movie_category.html',
                               category=categoryToDelete)


# READ - show movies in a category
@app.route('/categories/<int:category_id>/')
@app.route('/categories/<int:category_id>/items/')
def showMovies(category_id):
    """returns movies in specified category"""
    category = session.query(Category).filter_by(id=category_id).one()
    categories = session.query(Category).all()
    creator = getUserInfo(category.user_id)
    items = session.query(
        CatalogItem).filter_by(
            category_id=category_id).order_by(CatalogItem.id.desc())
    quantity = items.count()
    return render_template(
        'movie_catalog_menu.html',
        categories=categories,
        category=category,
        items=items,
        quantity=quantity,
        creator=creator)


# selecting specific movie in a catagory
@app.route('/categories/<int:category_id>/item/<int:catalog_item_id>/')
def showMovie(category_id, catalog_item_id):
    """returns specified movie"""
    category = session.query(Category).filter_by(id=category_id).one()
    item = session.query(CatalogItem).filter_by(id=catalog_item_id).one()
    creator = getUserInfo(category.user_id)
    return render_template('movie_catalog_menu_item.html',
                           category=category, item=item, creator=creator)


# CREATE Movie
@app.route('/categories/item/new', methods=['GET', 'POST'])
@login_required
def newMovie():
    """return "This page will be for adding new movie" """
    categories = session.query(Category).all()
    if request.method == 'POST':
        addNewItem = CatalogItem(
            name=request.form['name'],
            description=request.form['description'],
            category_id=request.form['category'],
            user_id=login_session['user_id'])
        session.add(addNewItem)
        session.commit()
        flash("New movie has been created!", 'success')
        return redirect(url_for('showMovieCatalog'))
    else:
        return render_template('new_movie.html', categories=categories)


# UPDATE Movie
@app.route(
    '/categories/<int:category_id>/item/<int:catalog_item_id>/edit',
    methods=['GET', 'POST'])
@login_required
def editMovie(category_id, catalog_item_id):
    """return "This page will be for updating a movie" """
    editedItem = session.query(CatalogItem).filter_by(id=catalog_item_id).one()
    if editedItem.user_id != login_session['user_id']:
        return """<script>function myFunction()
        {alert('You are not authorized for this function!')}
        </script><body onload='myFunction()'>"""
    if request.method == 'POST':
        if request.form['name']:
            editedItem.name = request.form['name']
        if request.form['description']:
            editedItem.description = request.form['description']
        if request.form['category']:
            editedItem.category_id = request.form['category']
        session.add(editedItem)
        session.commit()
        flash("Movie has been updated!", 'success')
        return redirect(url_for('showMovieCatalog'))
    else:
        categories = session.query(Category).all()
        return render_template('edit_movie.html', categories=categories,
                               item=editedItem)


# DELETE Movie
@app.route(
    '/categories/<int:category_id>/item/<int:catalog_item_id>/delete',
    methods=['GET', 'POST'])
@login_required
def deleteMovie(category_id, catalog_item_id):
    """return "This page will be for deleting a movie" """
    itemToDelete = session.query(
        CatalogItem).filter_by(id=catalog_item_id).one()
    if itemToDelete.user_id != login_session['user_id']:
        return """<script>function myFunction()
        {alert('Not Authorized for this function!')}
        </script><body onload='myFunction()'>"""
    if request.method == 'POST':
        session.delete(itemToDelete)
        session.commit()
        flash('Movie has been Successfully Deleted', 'success')
        return redirect(url_for('showMovieCatalog'))
    else:
        return render_template('delete_movie.html', item=itemToDelete)


# User helper functions
def getUserID(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None


def getUserInfo(user_id):
    user = session.query(User).filter_by(id=user_id).one()
    return user


def createUser(login_session):
    newUser = User(
        name=login_session['username'],
        email=login_session['email'],
        picture=login_session['picture'])
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id


# JSON APIs to show Movie Catalog information
@app.route('/catalog.json')
def showMovieCatalogJSON():
    """Returns JSON of all items in movie catalog"""
    items = session.query(CatalogItem).order_by(CatalogItem.id.desc())
    return jsonify(CatalogItems=[i.serialize for i in items])


@app.route(
    '/categories/<int:category_id>/item/<int:catalog_item_id>/JSON')
def movieJSON(category_id, catalog_item_id):
    """Returns JSON of selected item in movie catalog"""
    Catalog_Item = session.query(
        CatalogItem).filter_by(id=catalog_item_id).one()
    return jsonify(Catalog_Item=Catalog_Item.serialize)


@app.route('/categories/JSON')
def movieCategoriesJSON():
    """Returns JSON of all categories in movie catalog"""
    categories = session.query(Category).all()
    return jsonify(Categories=[r.serialize for r in categories])


if __name__ == '__main__':
    app.secret_key = 'my_secret_key'
    app.debug = True
    app.run(host='0.0.0.0', port=8000)
