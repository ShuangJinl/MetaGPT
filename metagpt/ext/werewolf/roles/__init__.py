#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Desc   :

from metagpt.ext.werewolf.roles.base_player import BasePlayer
from metagpt.ext.werewolf.roles.guard import Guard
from metagpt.ext.werewolf.roles.moderator import Moderator
from metagpt.ext.werewolf.roles.seer import Seer
from metagpt.ext.werewolf.roles.villager import Villager
from metagpt.ext.werewolf.roles.werewolf import Werewolf
from metagpt.ext.werewolf.roles.witch import Witch

__all__ = ["BasePlayer", "Guard", "Moderator", "Seer", "Villager", "Witch", "Werewolf"]
