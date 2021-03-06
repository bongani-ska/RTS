from fabric.api import sudo, run, env, cd
from fabric.contrib import files
import tempfile, shutil
import os

#GIT branch to use for deployment
GIT_BRANCH = 'master'

#Default location of Kat-7 svn repository
KAT_SVN_BASE = 'katfs.kat.ac.za'

# oodt install info
VAR_KAT = '/var/kat'
OODT_HOME = '/usr/local/oodt/'
STAGING_HOME = '/var/kat/data'
ARCHIVE_HOME = '/var/kat/archive'
SDP_MC = '/var/kat/sdpcontroller'
ARCHIVE_APACHE_HOME = '/var/www/archive'
# Subdirectories derived from roots
# Where we're going to put the oodt configuration files
OODT_CONF = os.path.join(OODT_HOME, "conf")
# Primary staging directory
SOLR_COLLECTIONS_HOME = os.path.join(ARCHIVE_HOME, "catalogs/solr")
STAGING_INGEST = os.path.join(STAGING_HOME, "staging")
# Where files go when ingest fails
STAGING_FAILED = os.path.join(STAGING_HOME, "failed")
# Secondary staging directory for remote archiving
STAGING_NFS_INGEST = os.path.join(STAGING_HOME, "nfs_staging")
# Archive directory where all the data products will be stored
ARCHIVE_DATA = os.path.join(ARCHIVE_HOME, "data")
# RTS storage directory where all the data products will be stored
RTS_DATA = os.path.join(ARCHIVE_DATA, "RTS")

#Solr and Tomcat

def install_deb_packages(packages):
    """Install debian packages listed in space-separated string"""
    print ' ---- Install debian packages ---- \n', packages, '\n'
    sudo('apt-get -y install %s' % (packages))

def remove_deb_packages(packages):
    """Remove debian packages listed in space-separated string"""
    print ' ---- Remove debian packages ---- \n', packages, '\n'
    sudo('apt-get -y remove %s' % (packages))

def install_pip_packages(packages, flags='-U'):
    """Pip install packages listed in space-separated string"""
    print ' ---- Install', packages, ' ---- \n'
    sudo('pip install '+flags+' %s' % (packages,))

def remove_pip_packages(packages):
    """Pip uninstall packages listed in space-separated string"""
    print ' ---- Uninstall', packages, ' ---- \n'
    try:
        sudo('yes | pip uninstall %s' % (packages))
    except:
        # we don't get a nice named exception if the package isn't there
        print 'Cannot uninstall \n'

def install_svn_package(package, user=None, password=None, base=KAT_SVN_BASE, flags='-I --no-deps', repo='svnDS', revision=None, **kwargs):
    """install svn package"""
    print ' ---- Install', package, ' ---- \n'
    #Make a temporary location to store the svn repo
    tempdir = tempfile.mkdtemp()
    retrieve_svn_package(package, user=user, password=password, base=base, repo=repo, revision=revision, output_location=tempdir)
    sudo('pip install '+tempdir)
    shutil.rmtree(tempdir)

def install_git_package(package, repo='ska-sa', login='katpull:katpull4git', branch='master', flags='-I --no-deps',**kwargs):
    """Install git packages directly using pip"""
    print ' ---- Install', package, ' ---- \n'
    if login:
        sudo('pip install '+ flags +' git+https://'+login+'@github.com/'+repo+'/'+package+'.git'+'@'+branch+'#egg='+package)
    else:
        sudo('pip install '+ flags +' git+https://github.com/'+repo+'/'+package+'.git@'+branch+'#egg='+package)

def retrieve_svn_package(package, user=None, password=None, base=KAT_SVN_BASE, repo='svnDS', revision=None, output_location=None):
    """Copy an svn repository to a specific location,
    overwriting contents of the output directory"""
    # Default package output location is the package name in the current directory
    if output_location is None:
        output_location = os.path.join(os.path.curdir,package)
    # Remove output location
    sudo('rm -rf '+output_location)
    print '\n ---- Retrieve', package, 'to', output_location, ' ---- \n'
    svn_command = 'svn co https://'+base+'/'+repo+'/'+package+' '+output_location
    if user is not None:
    	svn_command += ' --username='+user
    if password is not None:
    	svn_command += ' --password='+password
    if revision is not None:
    	svn_command += ' --revision='+str(revision)
    sudo(svn_command)

def update_svn_package(package, user=None, password=None, revision=None):
    """Copy an svn repository to a specific location,
    overwriting contents of the output directory"""
    print '\n ---- Update ' + package + ' ---- \n'
    svn_command = 'svn up ' + package
    if user is not None:
        svn_command += ' --username='+user
    if password is not None:
        svn_command += ' --password='+password
    if revision is not None:
        svn_command += ' --revision='+str(revision)
    sudo(svn_command)    

def retrieve_git_package(package, output_location=None, repo='ska-sa', login='katpull:katpull4git', branch='master', flags=''):
    """Copy a github repository to a specific location,
    overwriting contents of the output directory"""
    # Default package output location is the package name in the current directory
    if output_location is None:
        output_location = os.path.join(os.path.curdir,package)
    # Remove output location
    sudo('rm -rf '+output_location)
    print '\n ---- Retrieve', package, 'to', output_location, ' ---- \n'
    if login:
        sudo('git clone '+flags+' --branch '+branch+' https://'+login+'@github.com/'+repo+'/'+package+' '+output_location)
    else:
        sudo('git clone '+flags+' --branch '+branch+' https://github.com/'+repo+'/'+package+' '+output_location)

def configure_and_make(path, configure_options=None, make_options=None):
    """Run configure and make in a given path"""
    configure_command='./configure'
    make_command='make'
    if configure_options is not None:
        configure_command += ' ' + configure_options
    if make_options is not None:
        make_command += ' ' + make_options
    print configure_command,make_command
    #run configure and make
    with cd(path):
        sudo(configure_command)
        sudo(make_command)

def remove_dir(rmdir):
    sudo("rm -rf %s" % (rmdir,))

def make_directory(dir_to_make, options='-R'):
    sudo("mkdir -p %s" % (dir_to_make))
    sudo("chown %s %s %s" % (options, env.user, dir_to_make))
    sudo("chgrp %s %s %s" % (options, env.user, dir_to_make))

def deploy_tarball(comp_to_install, comp_ver):
    comp_tar = "%s-dist.tar.gz" % (comp_ver)
    run("rm -rf %s" % (os.path.join(OODT_HOME, comp_to_install)))
    run("wget -O /tmp/%s http://kat-archive.kat.ac.za/oodt_installs/%s" % (comp_tar, comp_tar))
    run("tar xzvf /tmp/%s -C %s" % (comp_tar, OODT_HOME))
    run("mv %s %s" % (os.path.join(OODT_HOME, comp_ver), os.path.join(OODT_HOME, comp_to_install)))
    run("rm -f /tmp/%s" % (comp_tar))

def deploy_oodt_comp_ver_06(comp_to_install):
    deploy_tarball(comp_to_install, "%s-0.6" % (comp_to_install))

def check_and_make_sym_link(L_src, L_dest):
    sudo("if [[ ! -L %s ]]; then ln -s %s %s; fi" % (L_dest, L_src, L_dest))

def export_dc_nfs_staging():
    files.append('/etc/exports',
                 '%s rts-imager.kat.ac.za(rw,sync,no_subtree_check)' % (STAGING_NFS_INGEST),
                 use_sudo=True)
    sudo('exportfs -a')

def remove_oodt_directories():
    remove_dir(OODT_HOME)
    remove_dir(ARCHIVE_HOME)
    remove_dir(ARCHIVE_APACHE_HOME)
    remove_dir(STAGING_HOME)
    remove_dir(SDP_MC)

def rsync(server, path_list, output_base='./', args='--compress --relative --no-motd --progress', force=False, use_sudo=False):
    """rsync a list of files from path_list from server to remote machine"""
    if not force:
        args = args + ' --ignore-existing'
    args = args + ' ' + server + '::"' + ' '.join(path_list) + '"'
    args = args + ' ' + output_base    # Download destination
    if use_sudo:
        sudo('rsync '+args)
    else:
        run('rsync ' + args)

#auto-startup of filemgr
def install_and_start_daemon(path, daemon):
    check_and_make_sym_link(os.path.join(path, daemon), os.path.join('/etc/init.d/', daemon))
    check_and_make_sym_link(os.path.join('/etc/init.d/', daemon), '/etc/rc2.d/S94' + daemon)
    check_and_make_sym_link(os.path.join('/etc/init.d/', daemon), '/etc/rc3.d/S94' + daemon)
    check_and_make_sym_link(os.path.join('/etc/init.d/', daemon), '/etc/rc0.d/K08' + daemon)
    check_and_make_sym_link(os.path.join('/etc/init.d/', daemon), '/etc/rc6.d/K08' + daemon)
    sudo(os.path.join('/etc/init.d/', daemon) + ' start')

def ntp_configuration():
    sudo('/etc/init.d/ntp stop')
    files.comment('/etc/ntp.conf',
               r'^server [0123]\.ubuntu\.pool\.ntp\.org$',
               use_sudo=True)
    files.comment('/etc/ntp.conf',
               r'^server ntp\.ubuntu\.com$',
               use_sudo=True)
    files.append('/etc/ntp.conf',
                 ['', '# KAT NTP servers',
                  'server ff-ntp.karoo.kat.ac.za prefer minpoll 4 maxpoll 6',
                  'server katfs.kat.ac.za minpoll 4 maxpoll 6'],
                   use_sudo=True)
    sudo('/etc/init.d/ntp start')
