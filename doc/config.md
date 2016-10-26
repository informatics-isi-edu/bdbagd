# ioboxd Configuration Guide
The service uses two files for configuration: `ioboxd_config.json` for service specific configuration and `wsgi_ioboxd.conf` to configure WSGI module support in Apache HTTPD.

### ioboxd_config.json
The installation and deployment process creates an `iobox` user on the local system, including a home directory for this user.  The service-specific configuration file `ioboxd_config.json` is located in this directory. 

Below is a sample of the default configuration file:

```json
{
    "storage_path": "/var/www/iobox/data",
    "authentication":"webauthn",
    "404_html": "<html><body><h1>Resource Not Found</h1><p>The requested resource could not be found at this location.</p><p>Additional information:</p><p><pre>%(message)s</pre></p></body></html>",
    "403_html": "<html><body><h1>Access Forbidden</h1><p>%(message)s</p></body></html>",
    "401_html": "<html><body><h1>Authentication Required</h1><p>%(message)s</p></body></html>",
    "400_html": "<html><body><h1>Bad Request</h1><p>One or more request parameters are incorrect.</p><p>Additional information:</p><p><pre>%(message)s</pre></p></body></html>"
}
```

* The `storage_path` variable is an absolute path to the base directory where the service stores file data.
* The `authentication` variable is an optional string value representing the authentication mechanism to use.  Valid values are `"webauthn"` or `None`, or the key can be ommitted, which is equivalent to specifiying `None`.
* The various `"*_html"` variables are for specifying customized HTML error template responses for API functions.

### wsgi_ioboxd.conf
The `wsgi_ioboxd.conf` file is installed to `/etc/httpd/conf.d`. Below is a sample of the default:
```
# this file must be loaded (alphabetically) after wsgi.conf
AllowEncodedSlashes On

WSGIPythonOptimize 1
WSGIDaemonProcess ioboxd processes=4 threads=4 user=iobox maximum-requests=2000
WSGIScriptAlias /iobox /usr/lib/python2.7/site-packages/ioboxd/ioboxd.wsgi
WSGIPassAuthorization On

WSGISocketPrefix /var/run/httpd/wsgi

<Location "/iobox" >
   Require all granted
   WSGIProcessGroup ioboxd
</Location>
```