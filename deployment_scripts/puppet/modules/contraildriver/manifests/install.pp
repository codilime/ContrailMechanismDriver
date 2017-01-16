class contraildriver::install {
  exec { 'setup ML2 mechanism driver':
    command => "/bin/sh install.sh",
    path    => $::path
  }
}
