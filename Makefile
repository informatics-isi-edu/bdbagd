
# this ugly hack necessitated by Ubuntu... grrr...
SYSPREFIX=$(shell python -c 'import site;print site.getsitepackages()[0]' | sed -e 's|/[^/]\+/[^/]\+/[^/]\+$$||')
# try to find the architecture-neutral lib dir by looking for one of our expected prereqs... double grrr...
PYLIBDIR=$(shell python -c 'import site;import os.path;print [d for d in site.getsitepackages() if os.path.exists(d+"/web")][0]')

CONFDIR=/etc
SHAREDIR=$(SYSPREFIX)/share/ioboxd

ifeq ($(wildcard /etc/httpd/conf.d),/etc/httpd/conf.d)
		HTTPSVC=httpd
else
		HTTPSVC=apache2
endif

HTTPDCONFDIR=/etc/$(HTTPSVC)/conf.d
WSGISOCKETPREFIX=/var/run/$(HTTPSVC)/wsgi
DAEMONUSER=iobox

# turn off annoying built-ins
.SUFFIXES:

INSTALL_SCRIPT=./install-script

UNINSTALL_DIRS=$(SHAREDIR)

UNINSTALL=$(UNINSTALL_DIRS)
#       $(BINDIR)/ioboxd-db-init

# make this the default target
install: conf/wsgi_ioboxd.conf
		pip install -I --process-dependency-links --trusted-host github.com  .

testvars:
		@echo DAEMONUSER=$(DAEMONUSER)
		@echo CONFDIR=$(CONFDIR)
		@echo SYSPREFIX=$(SYSPREFIX)
		@echo SHAREDIR=$(SHAREDIR)
		@echo HTTPDCONFDIR=$(HTTPDCONFDIR)
		@echo WSGISOCKETPREFIX=$(WSGISOCKETPREFIX)
		@echo PYLIBDIR=$(PYLIBDIR)

deploy: install
		env SHAREDIR=$(SHAREDIR) HTTPDCONFDIR=$(HTTPDCONFDIR) ioboxd-deploy

redeploy: uninstall deploy

conf/wsgi_ioboxd.conf: conf/wsgi_ioboxd.conf.in
		./install-script -M sed -R @PYLIBDIR@=$(PYLIBDIR) @WSGISOCKETPREFIX@=$(WSGISOCKETPREFIX) @DAEMONUSER@=$(DAEMONUSER) -o root -g root -m a+r -p -D $< $@

uninstall:
		-pip uninstall -y ioboxd
		rm -f /home/${DAEMONUSER}/ioboxd_config.json
		rm -f ${HTTPDCONFDIR}/wsgi_ioboxd.conf
		rm -f /etc/cron.daily/ioboxd-prune
#       -rmdir --ignore-fail-on-non-empty -p $(UNINSTALL_DIRS)

preinstall_centos:
		yum -y install python python-pip python-psycopg2 python-dateutil python-webpy pytz

preinstall_ubuntu:
		apt-get -y install python python-pip python-psycopg2 python-dateutil python-webpy python-tz

