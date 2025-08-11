-- This file contains the SQL commands needed to grant the correct permissions
-- to your 'dndadventure' database user.
--
-- Please log in to your MariaDB server as the root user. You can do this by running:
-- mysql -u root -p
--
-- After you have logged in, please run the following command.
-- This is one long line.
--
-- IMPORTANT: This command grants privileges to the user 'dndadventure' connecting
-- from the IP address '192.168.0.10', which was the IP address shown in your
-- Jenkins log. If your Jenkins server has a different IP address, you must
-- change '192.168.0.10' to the correct IP.
--
-- Also, replace 'yQ6b3qSEC3ttQT3rmKBrZtq21' with your actual database password
-- if it is different from what was in the Jenkins script.

GRANT ALL PRIVILEGES ON dndadventure.* TO 'dndadventure'@'192.168.0.10' IDENTIFIED BY 'yQ6b3qSEC3ttQT3rmKBrZtq21';

-- After running the GRANT command, run this final command to apply the changes:

FLUSH PRIVILEGES;

-- You can then type 'exit' to leave the MariaDB prompt.
