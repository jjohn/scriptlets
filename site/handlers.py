import wsgiref.handlers
from django.utils import simplejson
from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.api import urlfetch
from models import Script
import base64
import urllib

language_engines = {
    'php': 'http://scriptlets-engine.appspot.com/run.php',
    'javascript': 'http://scriptlets-engine.appspot.com/javascript/',
    'python': 'http://scriptlets-python.appspot.com/python/',
}

# ----------------------------------------
class EditHandler(webapp.RequestHandler):
   """
   handler for the /edit/ url
   """

   # -------------------
   def get(self, name):
       """
       uses the 'name' as key to obtain details from the datastore, then allows the user to edit it
       """
       q = Script.all().filter('name = ', name)
       user = users.get_current_user()
       #the user is logged in at this point, owing to 'login: required' setting in apps.yaml
       params = {}
       if user:
          params['user'] = user
          params['logout_url'] = users.create_logout_url("/")
          result = q.fetch(1)[0]
          params['language'] = result.language
          params['description'] = result.description
          params['user_friendly_name'] = result.user_friendly_name
          params['code'] = result.code.strip()
          params['name'] = result.name

          prev_scriptlets = False
          if Script.all().filter('user =', users.get_current_user()).count():
             #this user has previous saved scriptlets
             prev_scriptlets = True
          params['prev_scriptlets'] = prev_scriptlets

       self.response.out.write(template.render('templates/edit.html', params))

   # ---------------------
   def post(self, name):
        """
        deletes the old entry and iserts a new one with the same name and new updated values
        """
        language = self.request.POST['language']
        description = self.request.POST['description'].strip()
        user_friendly_name = self.request.POST['user_friendly_name'].strip()
        name = self.request.POST['name']

        code = self.request.POST['%s-code' % language].strip()
        #delete old entry
        q = Script.all().filter('name = ', name)
        for item in q:
           item.delete()
        script = Script(name=name, language=language, code=code, description=description or 'None', user_friendly_name=user_friendly_name or 'None')
        script.put()
        self.redirect('/saved/')

# ------------------------------------------
class SavedHandler(webapp.RequestHandler):
    """
    handler for the /saved/ url
    """

    # -------------
    def get(self):
       """
       gets a list of available scripts for the logged in user
       """
       q = Script.all().filter('user =', users.get_current_user())
       user = users.get_current_user()
       #the user is logged in at this point, owing to 'login: required' setting in apps.yaml
       params = {}
       params['user'] = user
       params['logout_url'] = users.create_logout_url("/")
       params['query'] = q
       prev_scriptlets = False
       if Script.all().filter('user =', users.get_current_user()).count():
          #this user has previous saved scriptlets
          prev_scriptlets = True
       params['prev_scriptlets'] = prev_scriptlets

       self.response.out.write(template.render('templates/saved.html', params))
    
    # --------------
    def post(self):
       """
       deletes an script that the logged in user dosen't want
       """
       for script_name in self.request.POST.items():
          if script_name[0] == 'delete':
             query_item = Script.all().filter('name =', script_name[1])
             if query_item.count() == 1:
                for item in query_item.fetch(1):
                 item.delete()
       self.redirect('/saved/') 

class ViewHandler(webapp.RequestHandler):
    def get(self):
        if self.request.path[-1] == '/':
            self.redirect(self.request.path[:-1])
        name = self.request.path.split('/')[-1]
        script = Script.all().filter('name =', name).get()

        prev_scriptlets = False
        if Script.all().filter('user =', users.get_current_user()).count():
           #this user has previous saved scriptlets
           prev_scriptlets = True

        if script:
            params = {'script':script, 'lines': script.code.count("\n"), 'run_url': self.request.url.replace('view', 'run')}
            user = users.get_current_user()
            if user:
                params['user'] = user
                params['logout_url'] = users.create_logout_url("/")
            else:
                params['user'] = user
                params['login_url'] = users.create_login_url('/')
            params['prev_scriptlets'] = prev_scriptlets
            self.response.out.write(template.render('templates/view.html', params))
        else:
            self.redirect('/')

class CodeHandler(webapp.RequestHandler):
    def get(self):
        if self.request.path[-1] == '/':
            self.redirect(self.request.path[:-1])
        name = self.request.path.split('/')[-1]
        script = Script.all().filter('name =', name).get()
        self.response.out.write(base64.b64encode(script.code))

class RunHandler(webapp.RequestHandler):
    def get(self):
        if self.request.path[-1] == '/':
            self.redirect(self.request.path[:-1])
        self._run_script()

    def post(self):
        self._run_script()
        
    def _run_script(self):
        name = self.request.path.split('/')[-1]
        script = Script.all().filter('name =', name).get()
        if script:
            payload = dict(self.request.POST)
            headers = dict(self.request.headers)
            if headers.get('Content-Type'):
                del headers['Content-Type']
            headers['Run-Code'] = base64.b64encode(script.code)
            headers['Run-Code-URL'] = self.request.url.replace('run', 'code')
            self.response.out.write(urlfetch.fetch(
                        url='%s?%s' % (language_engines[script.language], self.request.query_string),
                        payload=urllib.urlencode(payload) if len(payload) else None,
                        method=self.request.method,
                        headers=headers).content)
        else:
            self.redirect('/')


if __name__ == '__main__':
    wsgiref.handlers.CGIHandler().run(webapp.WSGIApplication([
    ('/view/.*', ViewHandler),
    ('/code/.*', CodeHandler),
    ('/saved/', SavedHandler),
    ('/edit/(.*)', EditHandler),
    ('/run/.*', RunHandler)], debug=True))
